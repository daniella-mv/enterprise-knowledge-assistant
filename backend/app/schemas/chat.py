"""Chat API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """User question + optional retrieval knobs."""

    message: str = Field(..., min_length=1, max_length=4000)
    top_k: int = Field(5, ge=1, le=20)


class Citation(BaseModel):
    """One source attached to a chat answer."""

    short_id: str  # "c_0", "c_1"...
    chunk_id: UUID
    document_id: UUID
    document_filename: str
    page: int
    snippet: str
    score: float
