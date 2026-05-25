# Design decisions

Short architecture decision records (ADRs). Each captures a choice, the
alternatives considered, and the consequences.

---

## ADR-001: pgvector over OpenSearch / Pinecone for the vector store

**Context.** The system needs vector similarity search and keyword
search, ideally fused into one ranked list.

**Decision.** Use Postgres with the `pgvector` extension for vectors
and `tsvector` for keyword search.

**Alternatives.**

- *OpenSearch Serverless.* Native hybrid search, AWS-managed.
  Minimum cost is in the hundreds of dollars per month even idle —
  unjustifiable for a single-tenant system at this scale.
- *Pinecone.* Hosted vector DB with a free tier. Adds vendor
  lock-in, separate ops surface, no native keyword search.
- *Qdrant / Weaviate / Milvus.* Self-hosted vector DBs. Strong
  performance, but operating two databases (relational + vector) for a
  small system is more complexity than the upside justifies.

**Consequences.** One database to operate. Hybrid retrieval is two
queries against the same engine. The HNSW index in pgvector is solid
at the scale this project targets (low-millions of chunks). Migration
to a dedicated vector store is a one-day adapter swap if scale changes.

---

## ADR-002: Hybrid retrieval (dense + sparse) with Reciprocal Rank Fusion

**Context.** Pure dense (embedding) retrieval misses queries with
specific tokens — numbers, proper nouns, acronyms. Pure sparse
(keyword) retrieval misses paraphrases. Hybrid retrieval consistently
outperforms either alone on RAG benchmarks.

**Decision.** Run dense kNN over `pgvector` and BM25-style search over
`tsvector` in parallel; fuse the two ranked lists with Reciprocal Rank
Fusion (RRF) at `k=60`.

**Alternatives.**

- *Pure dense.* Simpler, but loses recall on token-specific queries.
- *Pure sparse.* Fails on synonyms and paraphrasing.
- *Weighted score fusion.* Requires per-corpus weight tuning; RRF
  needs no tuning and produces comparable or better results in
  published benchmarks.
- *Cross-encoder reranking after fusion.* Better quality but adds
  serving cost. Documented as a future improvement.

**Consequences.** Two queries per retrieval, but they're cheap with
the HNSW + GIN indexes in place. RRF needs no tuning to defend.

---

## ADR-003: Local embeddings by default, Bedrock as a config swap

**Context.** Embedding cost is per-token and adds up during dev
iteration. Local embeddings remove that cost and keep dev offline-capable.

**Decision.** Implement an `EmbeddingProvider` interface with two
backends: `LocalEmbeddingProvider` (fastembed + `BAAI/bge-large-en-v1.5`)
and `BedrockEmbeddingProvider` (Titan v2). Selected by
`settings.embedding_provider`.

**Alternatives.**

- *Bedrock only.* Cleaner production story, but every dev iteration
  costs Bedrock tokens.
- *OpenAI ada-002.* Different vendor, different dimension, requires a
  separate API key.

**Consequences.** Both providers must produce 1024-dim vectors so the
column type and HNSW index are compatible across switches. fastembed
adds a one-time ~1.3GB model download (cached in a Docker volume).
The local model is good enough for development; the Bedrock path is
exercised by the smoke test.

---

## ADR-004: Synchronous ingestion in v1

**Context.** Real production RAG systems use async ingestion — uploads
hit S3, an event triggers a worker, the API doesn't hold the upload
connection open. That requires Lambda or ECS plumbing.

**Decision.** v1 ingests synchronously inside the API request: the
request returns once parse → chunk → embed → insert finishes.

**Alternatives.**

- *S3 → SQS → Lambda worker.* The right shape at scale. Out of scope
  for this build because it requires deployed AWS resources.
- *Background task in-process (FastAPI BackgroundTasks).* Half-step
  toward async; the API still has to keep state about in-progress
  ingestion.

**Consequences.** Documents under ~10MB index in seconds and the
synchronous response is fine. Larger documents would block the request.
The architecture doc spells out the async path for production.

---

## ADR-005: Citations as short ids in the prompt, UUIDs in the DB

**Context.** Models occasionally drop or mangle long opaque tokens.
Asking Claude to reproduce a 36-character UUID inline in an answer
fails too often to be reliable.

**Decision.** Assign each retrieved chunk a per-request short id
(`c_0`, `c_1`, ...) in the prompt. The model emits citations using
those short ids. The API parses `[c_<n>]` markers from the streamed
answer and resolves them to the original chunk records.

**Alternatives.**

- *Inline UUIDs.* Bad reproduction reliability.
- *Bare numeric ids (`[1]`, `[2]`).* Easy to confuse with footnotes
  or list numbering. The `c_` prefix is unambiguous.

**Consequences.** A small per-request mapping table; models reproduce
short ids accurately; the citation regex is trivial.

---

## ADR-006: SSE for chat streaming over WebSocket

**Context.** The chat endpoint streams tokens as Claude generates them.

**Decision.** Server-Sent Events. Unidirectional server-to-client is
sufficient; the request is fire-and-forget JSON, not a bidirectional
session.

**Alternatives.**

- *WebSocket.* Bidirectional, but overkill for a one-shot question.
  More moving parts (handshake, ping/pong, framing).
- *Long-polling.* No streaming; user waits for the full response.

**Consequences.** Plain HTTP/1.1 chunked encoding works through
proxies and CDNs. The browser uses `fetch` + `ReadableStream` because
`EventSource` is GET-only and we POST a JSON body.

---

## ADR-007: Alembic for migrations

**Context.** Database schema needs to evolve. Hand-applied SQL is
brittle.

**Decision.** Alembic with async-aware `env.py` running through the
same SQLAlchemy 2.0 async engine the application uses.

**Alternatives.**

- *SQLAlchemy `create_all()`.* No history, no rollback, can't safely
  evolve.
- *Hand-written SQL files.* Same problems, plus order management.

**Consequences.** One additional dev dependency. `make migrate` and
`make migrate-down` are part of the standard workflow. The HNSW index
and `tsvector` generated column are written as raw SQL in the
migrations because Alembic's autogenerate doesn't model them.
