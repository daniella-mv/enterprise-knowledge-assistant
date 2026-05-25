"""Hybrid retrieval.

Two retrieval strategies, fused via Reciprocal Rank Fusion (RRF):

  1. Dense  — cosine similarity over embeddings via pgvector
  2. Sparse — Postgres tsvector full-text search with ts_rank scoring

Dense search captures meaning ("annual leave" matches "PTO"); sparse
search captures specific tokens (numbers, proper nouns, acronyms). RRF
is the simplest fusion that doesn't require tuning weights between the
two scores.

RRF formula:
    score(d) = sum over lists of 1 / (k + rank(d, list))
with rank 1-indexed and k=60 as the standard default.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.embeddings import get_provider
from app.core.logging import get_logger
from app.models import Chunk, Document

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A chunk returned from retrieval, with source metadata for citations."""

    id: UUID
    document_id: UUID
    document_filename: str
    chunk_index: int
    page: int
    text: str
    score: float


def reciprocal_rank_fuse(
    ranked_lists: list[list[UUID]],
    *,
    k: int = 60,
) -> dict[UUID, float]:
    """Fuse multiple ranked lists by RRF. Returns id -> fused_score."""
    scores: dict[UUID, float] = {}
    for ranked in ranked_lists:
        for rank, doc_id in enumerate(ranked, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


async def hybrid_search(
    db: AsyncSession,
    query: str,
    *,
    owner_id: str,
    top_k: int = 5,
    candidate_k: int = 20,
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    """Run dense + sparse retrieval, fuse, and return top_k chunks.

    Args:
        db: open async session
        query: user question
        owner_id: scope retrieval to this user's documents only
        top_k: final result count after fusion
        candidate_k: per-strategy candidate count before fusion
        rrf_k: RRF dampening constant (60 is standard)
    """
    if not query.strip():
        return []

    log = logger.bind(owner_id=owner_id, query_preview=query[:80])

    # 1. Embed the query (one batch of size 1).
    provider = get_provider()
    [query_vec] = await provider.embed_batch([query])

    # 2. Dense (vector cosine distance).
    dense_stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.chunk_index,
            Chunk.page,
            Chunk.text,
            Document.filename,
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.owner_id == owner_id)
        .order_by(Chunk.embedding.cosine_distance(query_vec))
        .limit(candidate_k)
    )
    dense_rows = (await db.execute(dense_stmt)).all()

    # 3. Sparse (Postgres tsvector full-text search).
    ts_query = func.plainto_tsquery("english", query)
    sparse_stmt = (
        select(
            Chunk.id,
            Chunk.document_id,
            Chunk.chunk_index,
            Chunk.page,
            Chunk.text,
            Document.filename,
            func.ts_rank(Chunk.text_search, ts_query).label("rank"),
        )
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.owner_id == owner_id)
        .where(Chunk.text_search.op("@@")(ts_query))
        .order_by(func.ts_rank(Chunk.text_search, ts_query).desc())
        .limit(candidate_k)
    )
    sparse_rows = (await db.execute(sparse_stmt)).all()

    log.info(
        "retrieval_candidates",
        dense=len(dense_rows),
        sparse=len(sparse_rows),
    )

    # 4. Fuse: RRF over the two ordered ID lists.
    dense_ids = [row.id for row in dense_rows]
    sparse_ids = [row.id for row in sparse_rows]
    fused_scores = reciprocal_rank_fuse([dense_ids, sparse_ids], k=rrf_k)

    # 5. Build a lookup of every retrieved chunk's metadata (one row each).
    metadata: dict[UUID, dict] = {}
    for row in dense_rows:
        metadata[row.id] = {
            "document_id": row.document_id,
            "document_filename": row.filename,
            "chunk_index": row.chunk_index,
            "page": row.page,
            "text": row.text,
        }
    for row in sparse_rows:
        metadata.setdefault(
            row.id,
            {
                "document_id": row.document_id,
                "document_filename": row.filename,
                "chunk_index": row.chunk_index,
                "page": row.page,
                "text": row.text,
            },
        )

    # 6. Rank by fused score, take top_k.
    ranked_ids = sorted(fused_scores, key=fused_scores.get, reverse=True)[:top_k]
    return [
        RetrievedChunk(
            id=cid,
            score=fused_scores[cid],
            **metadata[cid],
        )
        for cid in ranked_ids
    ]
