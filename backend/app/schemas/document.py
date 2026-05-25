"""Document API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """Public document representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    status: str
    chunk_count: int
    file_size: int
    mime_type: str
    error: str | None
    created_at: datetime
    indexed_at: datetime | None


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    total: int
