# Cost analysis

Itemized costs for the current build at three usage levels. Local
development with the default configuration costs nothing.

## Components

| Component       | Local cost         | Production cost driver               |
|-----------------|--------------------|--------------------------------------|
| Postgres        | Free (Docker)      | RDS instance hours + storage         |
| Object storage  | Free (MinIO)       | S3 GB-month + requests               |
| Embeddings      | Free (fastembed)   | Bedrock Titan tokens, per-input      |
| Chat LLM        | Pay-per-token      | Bedrock Anthropic input + output     |
| API compute     | Free (Docker)      | Lambda invocations or Fargate hours  |
| Frontend host   | Free (Vite dev)    | CloudFront + S3 requests             |
| Logs / metrics  | Free (stdout)      | CloudWatch ingest + retention        |

## Pricing assumptions (May 2026)

| Item                                  | Unit price                |
|---------------------------------------|---------------------------|
| Bedrock Claude Haiku 4.5 input        | $0.80 per 1M tokens       |
| Bedrock Claude Haiku 4.5 output       | $4.00 per 1M tokens       |
| Bedrock Claude Sonnet 4.5 input       | $3.00 per 1M tokens       |
| Bedrock Claude Sonnet 4.5 output      | $15.00 per 1M tokens      |
| Bedrock Titan Text Embeddings v2      | $0.00002 per 1K tokens    |
| Amazon S3 standard storage            | $0.023 per GB-month       |
| Amazon RDS db.t4g.micro               | ~$13 per month            |
| Lambda                                | First 1M reqs free        |

A typical chat exchange uses about 4,000 input tokens (system prompt +
5 chunks of context + the question) and ~150 output tokens.

| Model    | Cost per question | Cost per 100 questions |
|----------|-------------------|------------------------|
| Haiku 4.5  | ~$0.0036          | ~$0.36                 |
| Sonnet 4.5 | ~$0.0143          | ~$1.43                 |

Embeddings are negligible: indexing a 5-page document is roughly 8
chunks × 600 tokens = ~5K tokens × $0.00002/1K = ~$0.0001 per
document.

## Three usage scenarios

### Scenario A — local dev, free tier

- All containers running on a developer laptop.
- Embeddings: local fastembed (no network calls).
- Chat: Haiku 4.5 via Bedrock, ~30 questions per day during
  development.

Monthly cost: ~30 × 30 days × $0.0036 = **~$3.24/month**.

### Scenario B — small team, hosted

- 5 users, ~50 questions per user per day, ~250 documents indexed.
- Storage: ~250 documents × ~1MB average = 250MB → ~$0.006/mo.
- Embeddings via Bedrock Titan: 250 docs × 5K tokens × $0.00002/1K =
  ~$0.025 (one-time on initial ingest).
- Chat: 50 × 5 × 30 = 7,500 questions/month × $0.0036 (Haiku) =
  **~$27/month**.
- RDS db.t4g.micro: ~$13/month.
- Lambda + S3 + CloudFront: stays under $5/month at this volume.

Monthly cost: **~$45/month** dominated by Bedrock chat.

### Scenario C — same as B but Sonnet 4.5

Replace Haiku with Sonnet at 7,500 questions/month: **~$107/month**
chat, ~$125/month total.

## Cost knobs

- **`top_k`** controls how many chunks join the prompt. Lower top_k
  reduces input tokens linearly. The eval harness shows top_k=1 saves
  ~80% of input tokens at a small recall cost on this corpus.
- **`CHUNK_SIZE`** affects per-chunk token count. Smaller chunks =
  more chunks per page = higher embedding cost on ingest, but only at
  ingestion time.
- **Model choice.** Haiku is ~4x cheaper than Sonnet with comparable
  quality on grounded RAG with citations enforced.
- **Embedding provider.** Local (fastembed) is free at the cost of
  CPU on the API host. Bedrock Titan is pennies but adds an external
  call to ingestion latency.

## What this build deliberately doesn't do

The cost model assumes Bedrock provisioned-throughput is **not**
purchased. On-demand pricing is used throughout. Provisioned
throughput is cheaper per token at high QPS but requires a 1-month or
6-month commitment that doesn't fit a single-tenant build.
