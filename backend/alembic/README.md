# Database migrations

Alembic-managed schema for the Enterprise Knowledge Assistant.

## Common commands

Run from the project root with the API container running:

```bash
# Apply all pending migrations
make migrate

# Roll back the last migration
make migrate-down

# Generate a new migration after editing models (review before committing!)
docker compose exec api uv run alembic revision --autogenerate -m "describe change"

# Show current revision
docker compose exec api uv run alembic current

# Show full history
docker compose exec api uv run alembic history
```

## Notes on the initial migration

Postgres extensions are created idempotently inside the migration so the
schema is fully self-contained. The HNSW index on `chunks.embedding` uses
`vector_cosine_ops`, which matches how we'll compute similarity at query
time. `m=16, ef_construction=64` are pgvector's recommended defaults for
balanced build cost vs. recall.
