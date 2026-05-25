"""Document ingestion orchestration.

The full pipeline:
    create Document(pending) -> upload to S3 -> parse -> chunk
    -> embed -> persist Chunks -> mark indexed

Failures during parse/chunk/embed mark the Document as `failed` with the
error string and return normally so the failed record persists. Only
true system failures (DB unavailable, etc.) bubble up as exceptions.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import storage
from app.adapters.embeddings import get_provider
from app.core.errors import IngestionError
from app.core.logging import get_logger
from app.models import Chunk, Document
from app.services import chunker, parser

logger = get_logger(__name__)


def _build_storage_key(owner_id: str, filename: str) -> str:
    """Namespaced, conflict-free storage path."""
    return f"documents/{owner_id}/{uuid4()}/{filename}"


async def ingest(
    db: AsyncSession,
    *,
    owner_id: str,
    filename: str,
    content: bytes,
    content_type: str | None,
) -> Document:
    """Full ingestion pipeline. Returns the Document with terminal status."""
    storage_key = _build_storage_key(owner_id, filename)

    doc = Document(
        owner_id=owner_id,
        filename=filename,
        storage_key=storage_key,
        status="pending",
        file_size=len(content),
        mime_type=content_type or "application/octet-stream",
    )
    db.add(doc)
    await db.flush()  # assigns doc.id

    log = logger.bind(document_id=str(doc.id), filename=filename)
    log.info("ingest_start", size=len(content))

    try:
        # 1. Persist raw bytes to object storage.
        await asyncio.to_thread(
            storage.put_object,
            storage_key,
            content,
            content_type=content_type or "application/octet-stream",
        )

        doc.status = "processing"
        await db.flush()

        # 2. Parse to pages with page numbers preserved.
        pages = parser.parse(filename, content, content_type)
        if not pages:
            raise IngestionError("no extractable text", code="empty_document")

        # 3. Chunk with token budget + overlap.
        produced = chunker.chunk_pages(pages)
        if not produced:
            raise IngestionError("no chunks produced", code="empty_chunks")

        # 4. Embed in one batch.
        provider = get_provider()
        vectors = await provider.embed_batch([c.text for c in produced])
        if len(vectors) != len(produced):
            raise IngestionError(
                f"embedding count mismatch: {len(vectors)} vs {len(produced)}",
                code="embedding_mismatch",
            )

        # 5. Persist chunks.
        for c, vec in zip(produced, vectors, strict=True):
            db.add(
                Chunk(
                    document_id=doc.id,
                    owner_id=owner_id,
                    chunk_index=c.chunk_index,
                    page=c.page,
                    text=c.text,
                    embedding=vec,
                )
            )

        doc.status = "indexed"
        doc.chunk_count = len(produced)
        doc.indexed_at = datetime.now(timezone.utc)
        await db.flush()

        log.info("ingest_done", chunk_count=len(produced))
        return doc

    except IngestionError as e:
        log.warning("ingest_failed", code=e.code, error=str(e))
        doc.status = "failed"
        doc.error = f"{e.code}: {str(e)[:500]}"
        await db.flush()
        return doc
    except Exception as e:  # noqa: BLE001 - downstream classification
        log.exception("ingest_unexpected_error")
        doc.status = "failed"
        doc.error = f"{type(e).__name__}: {str(e)[:500]}"
        await db.flush()
        return doc


async def delete_document(db: AsyncSession, doc: Document) -> None:
    """Best-effort delete from storage, then cascade-delete from DB."""
    try:
        await asyncio.to_thread(storage.delete_object, doc.storage_key)
    except Exception as e:  # noqa: BLE001 - storage misses are non-fatal
        logger.warning("storage_delete_failed", document_id=str(doc.id), error=str(e))
    await db.delete(doc)
    await db.flush()
