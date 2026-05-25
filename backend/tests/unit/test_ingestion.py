"""Tests for the ingestion service.

These exercise the orchestration logic with mocked storage, embedding,
and DB session — fast, deterministic, no model loads or network.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models import Document
from app.services import ingestion


class _FakeSession:
    """Minimal AsyncSession stub for unit testing."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushes = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, Document) and obj.id is None:
            # SQLAlchemy assigns id via column default on flush; mimic that.
            obj.id = uuid4()

    async def flush(self) -> None:
        self.flushes += 1
        for obj in self.added:
            if isinstance(obj, Document) and obj.id is None:
                obj.id = uuid4()

    async def delete(self, obj: Any) -> None:
        pass


@pytest.fixture
def patched_pipeline():
    """Patch out storage + embedding + parser/chunker for a clean unit test."""
    with (
        patch("app.services.ingestion.storage") as mock_storage,
        patch("app.services.ingestion.parser") as mock_parser,
        patch("app.services.ingestion.chunker") as mock_chunker,
        patch("app.services.ingestion.get_provider") as mock_get_provider,
    ):
        # parser returns 1 page
        mock_parser.parse.return_value = [MagicMock(page=1, text="some text")]
        # chunker returns 2 chunks
        mock_chunker.chunk_pages.return_value = [
            MagicMock(chunk_index=0, page=1, text="chunk a"),
            MagicMock(chunk_index=1, page=1, text="chunk b"),
        ]
        # embedding provider returns 2 vectors
        provider = MagicMock()
        provider.embed_batch = AsyncMock(return_value=[[0.1] * 1024, [0.2] * 1024])
        mock_get_provider.return_value = provider

        yield {
            "storage": mock_storage,
            "parser": mock_parser,
            "chunker": mock_chunker,
            "provider": provider,
        }


@pytest.mark.asyncio
async def test_ingest_happy_path_marks_indexed(patched_pipeline) -> None:
    db = _FakeSession()
    doc = await ingestion.ingest(
        db,  # type: ignore[arg-type]
        owner_id="alice",
        filename="handbook.pdf",
        content=b"%PDF-1.4 ...",
        content_type="application/pdf",
    )

    assert doc.status == "indexed"
    assert doc.chunk_count == 2
    assert doc.indexed_at is not None
    assert doc.error is None
    # 1 doc + 2 chunks added
    assert len([o for o in db.added if isinstance(o, Document)]) == 1
    # storage was called once with content bytes
    assert patched_pipeline["storage"].put_object.called


@pytest.mark.asyncio
async def test_ingest_unsupported_format_marks_failed(patched_pipeline) -> None:
    from app.core.errors import IngestionError

    patched_pipeline["parser"].parse.side_effect = IngestionError(
        "bad format", code="unsupported_format"
    )

    db = _FakeSession()
    doc = await ingestion.ingest(
        db,  # type: ignore[arg-type]
        owner_id="alice",
        filename="weird.xyz",
        content=b"...",
        content_type="application/octet-stream",
    )

    assert doc.status == "failed"
    assert doc.error is not None
    assert "unsupported_format" in doc.error


@pytest.mark.asyncio
async def test_ingest_empty_document_marks_failed(patched_pipeline) -> None:
    patched_pipeline["parser"].parse.return_value = []

    db = _FakeSession()
    doc = await ingestion.ingest(
        db,  # type: ignore[arg-type]
        owner_id="alice",
        filename="blank.pdf",
        content=b"%PDF-1.4 ...",
        content_type="application/pdf",
    )

    assert doc.status == "failed"
    assert doc.error is not None
    assert "empty_document" in doc.error


@pytest.mark.asyncio
async def test_ingest_embedding_count_mismatch(patched_pipeline) -> None:
    # Embedder returns only 1 vector but chunker produced 2
    patched_pipeline["provider"].embed_batch = AsyncMock(return_value=[[0.1] * 1024])

    db = _FakeSession()
    doc = await ingestion.ingest(
        db,  # type: ignore[arg-type]
        owner_id="alice",
        filename="ok.txt",
        content=b"hello",
        content_type="text/plain",
    )

    assert doc.status == "failed"
    assert "embedding_mismatch" in (doc.error or "")
