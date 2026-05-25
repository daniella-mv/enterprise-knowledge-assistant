"""FastAPI application factory.

Boot order: configure structured logging, build the app with CORS and
exception handlers, register routers. Each request gets a unique
request_id bound to the structlog context for log correlation.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.adapters.storage import ensure_bucket
from app.api.routes import chat, documents, health
from app.config import settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    logger.info(
        "startup",
        environment=settings.environment,
        version=settings.version,
        log_level=settings.log_level,
        s3_endpoint=settings.s3_endpoint_url or "aws-default",
        s3_bucket=settings.s3_bucket,
    )

    # Ensure the object-storage bucket exists. Best-effort at startup —
    # if storage is briefly unavailable we log and let the API come up;
    # request handlers that need storage will fail loudly with a 502.
    try:
        await asyncio.to_thread(ensure_bucket)
    except Exception as e:  # noqa: BLE001 - intentional broad catch at boot
        logger.warning("storage_unavailable_at_startup", error=str(e))

    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Enterprise Knowledge Assistant API",
        description="RAG-based knowledge assistant for internal documents.",
        version=settings.version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Bind a request_id and basic request metadata to the log context."""
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", code=exc.code, message=str(exc))
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    app.include_router(health.router, tags=["health"])
    app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

    return app


app = create_app()
