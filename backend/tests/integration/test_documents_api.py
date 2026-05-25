"""Integration tests for the documents API.

These exercise the real FastAPI stack — request parsing, dependency
injection, ORM, response serialization — against the running database
container. Tests roll back via the `db` fixture so they leave no trace.

Each test uses a unique owner_id (via `isolated_owner`) so previously
uploaded data on the running DB doesn't pollute results.

The ingestion service is patched per test so we don't load the
embedding model or hit MinIO during fast unit-test runs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


@pytest.fixture
def isolated_owner(monkeypatch: pytest.MonkeyPatch) -> str:
    """Each test gets a unique owner_id, patched into the route module.

    The route reads `_DEFAULT_OWNER_ID` at request time, so monkeypatching
    the module attribute swaps in the per-test value cleanly.
    """
    owner = f"test-{uuid4()}"
    monkeypatch.setattr("app.api.routes.documents._DEFAULT_OWNER_ID", owner)
    return owner


def _make_document(*, owner_id: str, **overrides: Any) -> Document:
    """Construct a Document with sensible defaults for tests."""
    base: dict[str, Any] = {
        "owner_id": owner_id,
        "filename": "handbook.txt",
        "storage_key": f"documents/{owner_id}/{uuid4()}/handbook.txt",
        "status": "indexed",
        "chunk_count": 1,
        "file_size": 42,
        "mime_type": "text/plain",
        "error": None,
        "indexed_at": datetime.now(timezone.utc),
    }
    base.update(overrides)
    return Document(**base)


# --- Upload --------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_returns_201_with_document(
    async_client: AsyncClient, isolated_owner: str
) -> None:
    fake_doc = _make_document(owner_id=isolated_owner)

    async def _fake_ingest(*args: Any, **kwargs: Any) -> Document:
        db = args[0]
        db.add(fake_doc)
        await db.flush()
        return fake_doc

    with patch(
        "app.api.routes.documents.ingestion.ingest", new=AsyncMock(side_effect=_fake_ingest)
    ):
        resp = await async_client.post(
            "/api/documents",
            files={"file": ("handbook.txt", b"hello world", "text/plain")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "handbook.txt"
    assert body["status"] == "indexed"
    assert UUID(body["id"])


@pytest.mark.asyncio
async def test_upload_rejects_missing_filename(async_client: AsyncClient) -> None:
    # FastAPI's multipart layer rejects an empty filename with 422 before
    # our handler runs; either client-error code is acceptable.
    resp = await async_client.post(
        "/api/documents",
        files={"file": ("", b"hello", "text/plain")},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/documents",
        files={"file": ("a.txt", b"", "text/plain")},
    )
    assert resp.status_code == 400


# --- List ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_only_owners_documents(
    async_client: AsyncClient,
    db: AsyncSession,
    isolated_owner: str,
) -> None:
    mine_a = _make_document(owner_id=isolated_owner, filename="mine_a.txt")
    mine_b = _make_document(owner_id=isolated_owner, filename="mine_b.txt")
    other = _make_document(owner_id="someone-else", filename="theirs.txt")
    db.add_all([mine_a, mine_b, other])
    await db.flush()

    resp = await async_client.get("/api/documents")
    assert resp.status_code == 200
    body = resp.json()
    filenames = [d["filename"] for d in body["items"]]
    assert "mine_a.txt" in filenames
    assert "mine_b.txt" in filenames
    assert "theirs.txt" not in filenames
    # Only the two owned by this test's owner.
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_list_orders_by_created_desc(
    async_client: AsyncClient,
    db: AsyncSession,
    isolated_owner: str,
) -> None:
    # All rows in one transaction share the same NOW(); we set timestamps
    # explicitly to test ordering deterministically.
    now = datetime.now(timezone.utc)
    older = _make_document(
        owner_id=isolated_owner,
        filename="older.txt",
        created_at=now - timedelta(hours=1),
    )
    newer = _make_document(
        owner_id=isolated_owner,
        filename="newer.txt",
        created_at=now,
    )
    db.add_all([older, newer])
    await db.flush()

    resp = await async_client.get("/api/documents")
    items = resp.json()["items"]
    idx_newer = next(i for i, d in enumerate(items) if d["filename"] == "newer.txt")
    idx_older = next(i for i, d in enumerate(items) if d["filename"] == "older.txt")
    assert idx_newer < idx_older


# --- Get -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_document_by_id(
    async_client: AsyncClient,
    db: AsyncSession,
    isolated_owner: str,
) -> None:
    doc = _make_document(owner_id=isolated_owner, filename="benefits.pdf")
    db.add(doc)
    await db.flush()

    resp = await async_client.get(f"/api/documents/{doc.id}")
    assert resp.status_code == 200
    assert resp.json()["filename"] == "benefits.pdf"


@pytest.mark.asyncio
async def test_get_returns_404_for_unknown_id(
    async_client: AsyncClient, isolated_owner: str
) -> None:
    resp = await async_client.get("/api/documents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_get_returns_404_for_other_owner(
    async_client: AsyncClient,
    db: AsyncSession,
    isolated_owner: str,
) -> None:
    other = _make_document(owner_id="someone-else", filename="theirs.txt")
    db.add(other)
    await db.flush()

    resp = await async_client.get(f"/api/documents/{other.id}")
    assert resp.status_code == 404


# --- Delete --------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_returns_204_and_removes_document(
    async_client: AsyncClient,
    db: AsyncSession,
    isolated_owner: str,
) -> None:
    doc = _make_document(owner_id=isolated_owner, filename="to-delete.txt")
    db.add(doc)
    await db.flush()
    doc_id = doc.id

    with patch("app.services.ingestion.storage.delete_object") as mock_delete:
        resp = await async_client.delete(f"/api/documents/{doc_id}")

    assert resp.status_code == 204
    assert mock_delete.called

    follow = await async_client.get(f"/api/documents/{doc_id}")
    assert follow.status_code == 404


@pytest.mark.asyncio
async def test_delete_returns_404_for_unknown_id(
    async_client: AsyncClient, isolated_owner: str
) -> None:
    resp = await async_client.delete(
        "/api/documents/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404
