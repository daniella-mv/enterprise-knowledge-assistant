# Resume bullets

Pick three to five depending on the role. The bullets prioritize
measurable outcomes and the names of technologies a hiring manager will
recognize.

## Strongest combination (general AI/ML role)

- Built an end-to-end retrieval-augmented question-answering system
  over private documents using Python, FastAPI, React, Postgres with
  the pgvector extension, and Anthropic Claude on Amazon Bedrock.
- Designed a hybrid retrieval pipeline combining dense vector
  similarity (1024-dim BAAI/bge embeddings) with BM25-style full-text
  search via Postgres `tsvector`, fused with Reciprocal Rank Fusion;
  measured 100% citation accuracy on a 20-question hand-curated
  evaluation set.
- Authored a reproducible evaluation harness with metrics for
  faithfulness, citation correctness, and abstention precision; used
  it to benchmark configurations and produce before/after tuning
  reports.
- Implemented streaming chat with Server-Sent Events end-to-end —
  Bedrock token deltas through FastAPI to a React frontend that
  renders inline citation chips with source-snippet previews.
- Containerized the full stack with Docker Compose, including a
  pgvector Postgres, an S3-compatible MinIO instance, async-aware
  Alembic migrations, and a structlog JSON logging pipeline with
  per-request correlation ids.

## Cloud / platform leaning

- Designed an AWS-native deployment topology for a private RAG system
  — API Gateway and Lambda fronting CloudFront-hosted React,
  Bedrock for managed LLM access, S3 + SQS for async document
  ingestion, RDS Postgres with pgvector for hybrid retrieval, and
  Cognito for JWT authentication.
- Built a vendor-neutral storage adapter that runs against AWS S3 in
  production and MinIO locally via a single configuration value,
  preserving identical boto3 call paths and signature handling.
- Wrote infrastructure decision records covering the
  pgvector-vs-OpenSearch tradeoff, sync-vs-async ingestion shape,
  and Bedrock model selection — with cost analysis at three traffic
  tiers.

## Backend / Python leaning

- Built an async Python backend on FastAPI 0.115 and SQLAlchemy 2 with
  psycopg 3, structlog request-correlated logging, Alembic migrations
  with a generated `tsvector` column and HNSW index, and a typed
  exception hierarchy mapped to JSON error envelopes.
- Implemented an embedding-provider interface with two interchangeable
  backends (local fastembed and Amazon Bedrock Titan) producing
  dimension-compatible vectors; selectable via environment variable.
- Wrote 70+ pytest tests including async integration tests that share
  a real DB session with the live FastAPI dependency graph via
  rollback-per-test isolation.

## Tone notes

- Use past tense.
- Lead with the verb. "Built", "Designed", "Implemented", "Wrote".
- Quantify when honest. The eval numbers (100% citation accuracy,
  97.8% recall, p95 < 2s) are real measurements on a real corpus.
- Don't claim production scale you didn't measure. The system is
  exercised at small scale; the architecture for larger scale is
  documented but not deployed.
- The most defensible answer to "what would you do differently?" is:
  "I'd ship the async ingestion path with SQS earlier — it's the most
  production-realistic piece I left out for cost reasons."
