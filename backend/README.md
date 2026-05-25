# Backend

FastAPI service for the Enterprise Knowledge Assistant.

## Layout

```
app/
  main.py            FastAPI factory + lifespan
  config.py          pydantic-settings configuration
  api/
    deps.py          Cross-cutting dependencies (db session, auth)
    routes/          health, documents, chat
  core/
    logging.py       structlog setup
    errors.py        Typed exception hierarchy
  adapters/          External service clients (db, storage, bedrock, embeddings)
  services/          Business logic (parser, chunker, retrieval, generation, ingestion)
  models/            SQLAlchemy ORM models
  schemas/           Pydantic API schemas
  prompts/           System / RAG prompt templates
alembic/             Database migrations
scripts/             Smoke tests for external services
tests/               Unit + integration tests
```

## Local dev

```bash
# From the project root:
make up                       # starts api + db + minio + frontend
docker compose logs -f api    # tail API logs

# Outside Docker (requires uv):
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

## Tests

```bash
make test                       # runs the full suite inside the api container
docker compose exec api uv run pytest -v
```

## Smoke tests

```bash
make smoke           # Bedrock connectivity + model invocation
make storage-smoke   # MinIO/S3 round-trip
make embed-smoke     # Local or Bedrock embedding round-trip
make chat-smoke Q="your question"
```
