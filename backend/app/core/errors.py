"""Typed exception hierarchy.

Each exception carries a stable `code` string so callers and metric
filters can react to specific failure modes without parsing the
human-readable message. The handler in app.main turns these into
structured JSON error responses.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for all application-defined errors."""

    code: str = "internal_error"
    status_code: int = 500

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message or self.__class__.__name__)
        if code:
            self.code = code


class IngestionError(AppError):
    code = "ingestion_error"
    status_code = 500


class RetrievalError(AppError):
    code = "retrieval_error"
    status_code = 500


class GenerationError(AppError):
    """Raised when the upstream LLM fails or returns an unusable response."""

    code = "generation_error"
    status_code = 502


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class AuthError(AppError):
    code = "unauthorized"
    status_code = 401
