"""add tsvector column + GIN index for keyword search

Adds a generated `text_search` column to chunks so we can do BM25-style
full-text search alongside vector similarity. The generated column is
maintained automatically by Postgres whenever `text` changes, so we
never have to remember to keep it in sync.

The GIN index makes `@@` (text-match) queries on `text_search` fast.

Revision ID: 0002_text_search
Revises: 0001_initial
Create Date: 2026-05-01
"""
from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "0002_text_search"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE chunks
        ADD COLUMN text_search tsvector
          GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX ix_chunks_text_search
        ON chunks USING gin (text_search)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_text_search")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS text_search")
