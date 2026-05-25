"""SQLAlchemy declarative base.

Every ORM model in this app inherits from `Base`. Centralizing this
also gives us one `Base.metadata` object that Alembic can introspect.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
