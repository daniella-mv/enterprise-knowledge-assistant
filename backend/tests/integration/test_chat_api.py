"""Integration tests for the chat endpoint.

Bedrock is mocked so tests run offline + deterministically. We verify:
  * SSE token events stream out in order
  * Citations are extracted from the model output and resolved correctly
  * Empty message is rejected
  * Errors from Bedrock surface as `event: error` instead of crashing
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import GenerationError
from app.models import Chunk, Document
from app.services.retrieval import RetrievedChunk


@pytest.fixture
def patched_query_embedding():
    """Return a deterministic 1024-dim query vector."""
    provider = AsyncMock()
    provider.embed_batch = AsyncMock(return_value=[[1.0] + [0.0] * 1023])
    with patch("app.services.retrieval.get_provider", return_value=provider):
        yield


def _make_doc(owner_id: str, filename: str = "handbook.pdf") -> Document:
    return Document(
        owner_id=owner_id,
        filename=filename,
        storage_key=f"documents/{owner_id}/{uuid4()}/{filename}",
        status="indexed",
        chunk_count=1,
        file_size=100,
        mime_type="application/pdf",
    )


def _seed_pto_doc(db: AsyncSession, owner_id: str) -> RetrievedChunk:
    """Insert one chunk we can match. Returns its expected RetrievedChunk shape."""
    doc = _make_doc(owner_id)
    db.add(doc)
    return RetrievedChunk(
        id=uuid4(),  # placeholder; the real chunk gets a fresh id
        document_id=doc.id,
        document_filename=doc.filename,
        chunk_index=0,
        page=7,
        text="Employees receive fifteen PTO days per year.",
        score=1.0,
    )


async def _fake_stream(*args: Any, **kwargs: Any) -> AsyncIterator[str]:
    """A canned Bedrock response that cites c_0."""
    for delta in ["Employees ", "get ", "15 ", "PTO ", "days [c_0]."]:
        yield delta


@pytest.mark.asyncio
async def test_chat_streams_tokens_and_returns_citations(
    async_client: AsyncClient,
    db: AsyncSession,
    patched_query_embedding: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seed a chunk owned by the test default owner.
    from app.api.routes.chat import _DEFAULT_OWNER_ID

    doc = _make_doc(_DEFAULT_OWNER_ID)
    db.add(doc)
    await db.flush()
    chunk = Chunk(
        document_id=doc.id,
        owner_id=_DEFAULT_OWNER_ID,
        chunk_index=0,
        page=7,
        text="Employees receive fifteen PTO days per year.",
        embedding=[1.0] + [0.0] * 1023,
    )
    db.add(chunk)
    await db.flush()

    with patch("app.adapters.bedrock.stream_chat", side_effect=_fake_stream):
        async with async_client.stream(
            "POST", "/api/chat", json={"message": "PTO policy?"}
        ) as resp:
            assert resp.status_code == 200
            tokens: list[str] = []
            done_payload: str | None = None
            event = None
            async for line in resp.aiter_lines():
                if not line:
                    event = None
                    continue
                if line.startswith("event:"):
                    event = line.removeprefix("event:").strip()
                elif line.startswith("data:"):
                    data = line.removeprefix("data:").strip()
                    if event == "token":
                        tokens.append(data)
                    elif event == "done":
                        done_payload = data

    answer = "".join(tokens)
    assert "Employees" in answer
    assert "[c_0]" in answer
    assert done_payload is not None

    import json as _json

    citations = _json.loads(done_payload)["citations"]
    assert len(citations) == 1
    assert citations[0]["short_id"] == "c_0"
    assert citations[0]["document_filename"] == doc.filename
    assert citations[0]["page"] == 7


@pytest.mark.asyncio
async def test_chat_rejects_empty_message(async_client: AsyncClient) -> None:
    resp = await async_client.post("/api/chat", json={"message": ""})
    # Pydantic validation kicks in (min_length=1)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_chat_emits_error_event_on_bedrock_failure(
    async_client: AsyncClient,
    db: AsyncSession,
    patched_query_embedding: Any,
) -> None:
    async def _failing_stream(*args: Any, **kwargs: Any) -> AsyncIterator[str]:
        raise GenerationError("simulated bedrock outage")
        yield  # pragma: no cover - unreachable, satisfies type checker

    with patch("app.adapters.bedrock.stream_chat", side_effect=_failing_stream):
        async with async_client.stream(
            "POST", "/api/chat", json={"message": "anything"}
        ) as resp:
            assert resp.status_code == 200
            saw_error = False
            event = None
            async for line in resp.aiter_lines():
                if not line:
                    event = None
                    continue
                if line.startswith("event:"):
                    event = line.removeprefix("event:").strip()
                elif line.startswith("data:") and event == "error":
                    saw_error = True

    assert saw_error
