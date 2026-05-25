"""Chunk ORM model.

A chunk is a slice of a document (~800 tokens) plus the embedding vector
that lets us do similarity search.

EMBEDDING_DIM is fixed at 1024 because:
  - Bedrock Titan Text Embeddings v2 produces 1024-dim vectors by default
  - sentence-transformers BAAI/bge-large-en-v1.5 also produces 1024-dim
  - Keeping both providers at the same dimension lets us swap without
    recreating the column / re-indexing every chunk.

owner_id is denormalized from documents.owner_id so retrieval queries
can filter on it without joining. At query time we fetch chunks scoped
to a single user; the JOIN would be expensive at scale.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.document import Document


EMBEDDING_DIM = 1024


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    # Auto-maintained by Postgres via GENERATED ALWAYS AS (...) STORED.
    # Used for BM25-style keyword search with the @@ operator.
    text_search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', text)", persisted=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Chunk id={self.id} doc={self.document_id} idx={self.chunk_index}>"
