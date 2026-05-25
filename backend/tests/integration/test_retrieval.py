"""Integration tests for hybrid retrieval against the live DB.

Uses synthetic chunks with hand-crafted embeddings so behavior is
deterministic — no model loads, no flakiness.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document
from app.services.retrieval import hybrid_search


def _make_doc(owner_id: str, filename: str) -> Document:
    return Document(
        owner_id=owner_id,
        filename=filename,
        storage_key=f"documents/{owner_id}/{uuid4()}/{filename}",
        status="indexed",
        chunk_count=0,
        file_size=100,
        mime_type="text/plain",
    )


def _emb(seed: float) -> list[float]:
    """Deterministic 1024-dim vector. The first dim carries the signal so
    tests can predict cosine ordering."""
    return [seed] + [0.0] * 1023


@pytest.fixture
def patched_query_embedding(request: pytest.FixtureRequest):
    """Replace the embedding provider so the query vector is deterministic."""
    seed = getattr(request, "param", 1.0)
    provider = AsyncMock()
    provider.embed_batch = AsyncMock(return_value=[_emb(seed)])
    with patch("app.services.retrieval.get_provider", return_value=provider):
        yield


@pytest.mark.asyncio
async def test_returns_empty_for_empty_query(db: AsyncSession) -> None:
    result = await hybrid_search(db, "", owner_id="anyone")
    assert result == []


@pytest.mark.asyncio
async def test_returns_empty_when_no_chunks(
    db: AsyncSession, patched_query_embedding: Any
) -> None:
    result = await hybrid_search(db, "anything", owner_id="lonely-user")
    assert result == []


@pytest.mark.asyncio
async def test_filters_by_owner(
    db: AsyncSession, patched_query_embedding: Any
) -> None:
    owner = f"owner-{uuid4()}"
    other = f"other-{uuid4()}"

    # Two documents owned by different users
    doc_owner = _make_doc(owner, "owners.txt")
    doc_other = _make_doc(other, "others.txt")
    db.add_all([doc_owner, doc_other])
    await db.flush()

    # Each gets one chunk with the same content
    db.add(
        Chunk(
            document_id=doc_owner.id,
            owner_id=owner,
            chunk_index=0,
            page=1,
            text="The quick brown fox.",
            embedding=_emb(1.0),
        )
    )
    db.add(
        Chunk(
            document_id=doc_other.id,
            owner_id=other,
            chunk_index=0,
            page=1,
            text="The quick brown fox.",
            embedding=_emb(1.0),
        )
    )
    await db.flush()

    results = await hybrid_search(db, "quick fox", owner_id=owner, top_k=10)
    assert len(results) == 1
    assert results[0].document_filename == "owners.txt"


@pytest.mark.asyncio
async def test_returns_top_k_with_score_descending(
    db: AsyncSession, patched_query_embedding: Any
) -> None:
    owner = f"owner-{uuid4()}"
    doc = _make_doc(owner, "policies.txt")
    db.add(doc)
    await db.flush()

    # 5 chunks, content varied so keyword search differentiates them.
    contents = [
        "Employees get fifteen PTO days per year",
        "Multi-factor authentication is required for production access",
        "401(k) matching up to four percent of base salary",
        "Helpdesk tickets are triaged within one business hour",
        "All passwords must be at least twelve characters long",
    ]
    for i, text in enumerate(contents):
        db.add(
            Chunk(
                document_id=doc.id,
                owner_id=owner,
                chunk_index=i,
                page=1,
                text=text,
                # Same embedding for everyone so dense search ties; sparse
                # is the differentiator.
                embedding=_emb(1.0),
            )
        )
    await db.flush()

    results = await hybrid_search(db, "PTO days", owner_id=owner, top_k=3)

    assert 1 <= len(results) <= 3
    # Ordered by score descending
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    # The PTO chunk should be first (sparse search will rank it on top).
    assert "PTO" in results[0].text


@pytest.mark.asyncio
async def test_dense_only_match_still_returned(
    db: AsyncSession, patched_query_embedding: Any
) -> None:
    """A chunk that nobody keyword-matches should still be returned via
    dense search if its embedding is closest."""
    owner = f"owner-{uuid4()}"
    doc = _make_doc(owner, "policies.txt")
    db.add(doc)
    await db.flush()

    db.add(
        Chunk(
            document_id=doc.id,
            owner_id=owner,
            chunk_index=0,
            page=1,
            text="completely unrelated lorem ipsum content",
            embedding=_emb(1.0),  # query is also _emb(1.0) -> distance 0
        )
    )
    await db.flush()

    # Query terms don't appear in the chunk -> sparse match empty.
    # Dense match still returns it because the embedding aligns.
    results = await hybrid_search(db, "PTO benefits", owner_id=owner)
    assert len(results) == 1
    assert "lorem ipsum" in results[0].text
