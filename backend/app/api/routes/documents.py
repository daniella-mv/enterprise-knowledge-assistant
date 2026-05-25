"""Documents API.

POST   /api/documents          upload + ingest
GET    /api/documents          list (most recent first)
GET    /api/documents/{id}     detail
DELETE /api/documents/{id}     remove from storage + DB
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.errors import NotFoundError
from app.models import Document
from app.schemas.document import DocumentList, DocumentResponse
from app.services import ingestion

router = APIRouter()

# TODO: replace with authenticated user_id once auth is wired up.
_DEFAULT_OWNER_ID = "local-user"


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
) -> Document:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")

    doc = await ingestion.ingest(
        db,
        owner_id=_DEFAULT_OWNER_ID,
        filename=file.filename,
        content=content,
        content_type=file.content_type,
    )
    return doc


@router.get("", response_model=DocumentList)
async def list_documents(
    db: AsyncSession = Depends(get_db_session),
) -> DocumentList:
    stmt = (
        select(Document)
        .where(Document.owner_id == _DEFAULT_OWNER_ID)
        .order_by(Document.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    total_stmt = (
        select(func.count())
        .select_from(Document)
        .where(Document.owner_id == _DEFAULT_OWNER_ID)
    )
    total = (await db.execute(total_stmt)).scalar_one()

    return DocumentList(
        items=[DocumentResponse.model_validate(d) for d in rows],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> Document:
    doc = await db.get(Document, document_id)
    if doc is None or doc.owner_id != _DEFAULT_OWNER_ID:
        raise NotFoundError("document not found")
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    doc = await db.get(Document, document_id)
    if doc is None or doc.owner_id != _DEFAULT_OWNER_ID:
        raise NotFoundError("document not found")
    await ingestion.delete_document(db, doc)
