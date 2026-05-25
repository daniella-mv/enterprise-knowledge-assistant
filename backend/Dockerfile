# Backend API image.
# Uses uv for fast, reproducible installs.
FROM python:3.12-slim AS base

# Install uv (single static binary).
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install system deps. psycopg-binary already ships its own libpq, so the
# slim base is enough.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cache-friendly layer).
COPY pyproject.toml ./
COPY README.md ./
RUN uv sync --no-install-project

# Copy application source + Alembic migration tooling.
COPY app ./app
COPY scripts ./scripts
COPY tests ./tests
COPY alembic ./alembic
COPY alembic.ini ./

# Install the project itself (now that source is present).
RUN uv sync

EXPOSE 8000

# docker-compose.yml overrides this with --reload for local dev.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
