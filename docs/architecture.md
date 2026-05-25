# Architecture

## Components

| Service       | Role                                                          |
|---------------|---------------------------------------------------------------|
| `frontend`    | React + Vite SPA. Talks to the API over HTTPS / SSE.          |
| `api`         | FastAPI. All business logic; thin route layer over services.  |
| `db`          | Postgres 16 + `pgvector` + `tsvector`. Documents, chunks, vectors. |
| `minio`       | S3-compatible object storage for raw uploads.                 |
| Bedrock       | Anthropic Claude (chat) + Titan v2 (embeddings, optional).    |
| fastembed     | Local ONNX embedding model (`BAAI/bge-large-en-v1.5`, 1024 dim). |

Each is a Docker container in local development; in production the API
fronts behind an API Gateway / load balancer, the DB is RDS, MinIO is
replaced by AWS S3, and the embedding model can stay local on the API
host or move to Bedrock with one config change.

## Data model

```
documents                          chunks
─────────────                      ─────────────
id              uuid (PK)          id              uuid (PK)
owner_id        varchar(128)       document_id     uuid (FK -> documents.id, ON DELETE CASCADE)
filename        varchar(512)       owner_id        varchar(128)        -- denormalized
storage_key     varchar(1024)      chunk_index     integer             -- 0-indexed
status          varchar(32)        page            integer             -- 1-indexed source page
chunk_count     integer            text            text
error           text               embedding       vector(1024)        -- pgvector
file_size       integer            text_search     tsvector            -- generated from text
mime_type       varchar(128)       created_at      timestamptz
created_at      timestamptz
indexed_at      timestamptz?
```

`status` is a state machine: `pending → processing → indexed | failed`.
Failures retain the row with the error string for debugging.

`owner_id` is denormalized into the chunks table so retrieval queries
filter on it directly without joining. The cost is one extra column at
write time; the benefit is simpler, faster, predicate-pushdown-friendly
queries at retrieval time.

`text_search` is a `tsvector` generated column maintained by Postgres
(`GENERATED ALWAYS AS (to_tsvector('english', text)) STORED`). A GIN
index on it makes BM25-style keyword retrieval cheap.

`embedding` has an HNSW index using `vector_cosine_ops`:

```sql
CREATE INDEX ix_chunks_embedding_hnsw
ON chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

## Ingestion flow

```
Browser ───multipart upload──▶ FastAPI POST /api/documents
                                    │
                                    ▼
                              create row (status=pending)
                                    │
                                    ▼
                           ┌────────────────┐
                           │  put_object    │──▶  MinIO / S3
                           └────────────────┘
                                    │  status=processing
                                    ▼
                           ┌────────────────┐
                           │     parse      │   pypdf / python-docx / plain text
                           └────────────────┘
                                    │   list[ParsedPage]
                                    ▼
                           ┌────────────────┐
                           │     chunk      │   tiktoken-counted, ~800 tokens, 100 overlap
                           └────────────────┘
                                    │   list[Chunk]
                                    ▼
                           ┌────────────────┐
                           │     embed      │   fastembed (local) or Bedrock Titan
                           └────────────────┘
                                    │   list[list[float]]  (1024-dim each)
                                    ▼
                           bulk INSERT chunks (text + embedding)
                                    │   status=indexed, chunk_count=N
                                    ▼
                              return Document JSON
```

Failures during parse/chunk/embed mark the document `failed` with the
error string and return normally so the row persists for debugging.
True system errors (DB unavailable) bubble up as 500s.

In production, the same shape is split across S3 → SQS → a worker
Lambda so the API doesn't hold the upload connection open during
embedding. The worker writes the same rows; the API just polls or
subscribes to status changes.

## Query flow

```
Browser ──POST /api/chat (JSON)──▶ FastAPI
                                       │
                                       ▼
                                 embed(query)               (one batch of 1)
                                       │
                                       ▼
                  ┌────────────────────┴────────────────────┐
                  │                                         │
                  ▼                                         ▼
        kNN cosine over chunks.embedding         tsvector @@ plainto_tsquery
        (top-K, owner_id filter)                 (top-K, ts_rank scoring)
                  │                                         │
                  └────────────────┬────────────────────────┘
                                   ▼
                           Reciprocal Rank Fusion
                           score(d) = Σ 1/(k+rank), k=60
                                   │
                                   ▼
                          top_k chunks + metadata
                                   │
                                   ▼
                       build_rag_prompt(question, chunks)
                          (wraps each chunk in <context id="c_<n>">)
                                   │
                                   ▼
                       Bedrock invoke_model_with_response_stream
                          system prompt enforces grounding + citation format
                                   │
                                   ▼ stream text deltas
                            FastAPI yields SSE events
                              event: token  data: <delta>
                              ...
                              event: done   data: {citations: [...]}
                                   │
                                   ▼
                                 Browser
                          (renders tokens; resolves [c_n] markers
                           against the citation panel)
```

## Citations

Each retrieved chunk receives a stable short id (`c_0`, `c_1`, ...) for
the duration of the request. The system prompt instructs Claude to cite
every factual claim using these short ids. After streaming completes,
the API parses `[c_<n>]` markers from the answer text and resolves them
back to `(document_filename, page, snippet)` for the response payload.

UUIDs are used at the database layer; the short-id mapping exists only
in-flight per request. Models reproduce short ids reliably; full UUIDs
get mangled.

## Production deployment shape

The local Docker Compose stack is a 1:1 model of the production
topology. Production swaps:

| Local                | Production                                |
|----------------------|-------------------------------------------|
| Docker `db` service  | Amazon RDS Postgres (with `pgvector`)     |
| MinIO container      | Amazon S3 bucket (with KMS encryption)    |
| Local API container  | API Gateway + Lambda or ECS Fargate       |
| Browser → Vite proxy | CloudFront → S3 (static SPA)              |
| Sync ingestion       | S3 ObjectCreated → SQS → worker Lambda    |
| (none)               | Cognito user pool for JWT-based auth      |
| (none)               | CloudWatch dashboards + X-Ray traces      |

`infra/terraform/` is reserved for the Terraform that would deploy this
shape. It is intentionally out of scope for the current build to keep
running costs at zero.
