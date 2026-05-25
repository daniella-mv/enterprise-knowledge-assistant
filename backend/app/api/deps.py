"""FastAPI dependency providers.

Centralizes cross-cutting dependencies so route modules import them
from one place.
"""

from app.adapters.db import get_db_session

__all__ = ["get_db_session"]

