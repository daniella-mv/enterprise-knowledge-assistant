"""Async SQLAlchemy engine and session factory.

Uses SQLAlchemy 2.0's async API on top of psycopg 3, which speaks both
sync and async natively. The same DATABASE_URL works for sync (Alembic
migrations) and async (the API).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# Single engine per process. SQLAlchemy manages a connection pool internally.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,           # set True to log every SQL statement when debugging
    pool_size=10,         # baseline connections kept open
    max_overflow=10,      # extras allowed during burst
    pool_pre_ping=True,   # validate connections before use; recovers from idle drops
)

# Session factory. expire_on_commit=False means objects stay usable after commit
# (otherwise SQLAlchemy invalidates them and accessing attributes would re-query).
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Yields a session, commits on success, rolls back on error.

    Usage:
        @router.get("/foo")
        async def handler(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
