-- Initial database setup. Runs once when the postgres volume is first created.
-- Schema and tables are added in Phase 2 via SQLAlchemy/Alembic migrations.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Quick sanity-check table; can be removed in Phase 2.
CREATE TABLE IF NOT EXISTS bootstrap_check (
    id SERIAL PRIMARY KEY,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO bootstrap_check (note) VALUES ('pgvector + uuid-ossp ready');
