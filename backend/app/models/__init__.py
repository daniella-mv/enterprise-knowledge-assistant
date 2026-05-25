"""SQLAlchemy ORM models.

Importing the package surfaces every model so `Base.metadata` is fully
populated — Alembic relies on this to autogenerate accurate migrations.
"""

from app.models.base import Base
from app.models.chunk import EMBEDDING_DIM, Chunk
from app.models.document import Document, DocumentStatus

__all__ = ["Base", "Chunk", "Document", "DocumentStatus", "EMBEDDING_DIM"]
