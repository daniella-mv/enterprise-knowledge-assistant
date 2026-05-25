# Deployment

This project ships with a Docker Compose stack for local development.
A production deployment to AWS is out of scope for this build, but the
local stack is a 1:1 shape of what the production deployment would
look like; this doc explains both.

## Local

Prerequisites: Docker Desktop. Optional: AWS credentials with Bedrock
model access (only needed for the chat endpoint and the embedding
smoke test against Bedrock).

```bash
git clone <repo> enterprise-knowledge-assistant
cd enterprise-knowledge-assistant
cp .env.example .env

# fill in AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in .env if you
# plan to use Bedrock for chat or embeddings.

make up                           # build + start all containers
make migrate                      # apply database schema
```

Verify:

```bash
make ps                           # all containers should report "healthy"
make test                         # full test suite (~70 tests)
make smoke                        # Bedrock connectivity (requires AWS creds)
make storage-smoke                # MinIO round-trip
make embed-smoke                  # local or Bedrock embedding round-trip
make chat-smoke Q="anything"      # end-to-end RAG (requires AWS creds)
```

URLs:

| Service       | URL                          |
|---------------|------------------------------|
| Frontend      | <http://localhost:5173>      |
| API docs      | <http://localhost:8000/docs> |
| MinIO console | <http://localhost:9001>      |

## Configuration

All configuration is environment-variable based, loaded by
`pydantic-settings` from `.env` at API startup. Key variables:

| Variable                          | Purpose                                              |
|-----------------------------------|------------------------------------------------------|
| `DATABASE_URL`                    | Postgres connection string                           |
| `AWS_REGION`                      | Region for Bedrock + S3                              |
| `AWS_ACCESS_KEY_ID` / `_SECRET_`  | IAM credentials                                      |
| `BEDROCK_TEXT_MODEL_ID`           | Cross-region inference profile id                    |
| `BEDROCK_EMBEDDING_MODEL_ID`      | Titan v2 model id                                    |
| `EMBEDDING_PROVIDER`              | `local` or `bedrock`                                 |
| `EMBEDDING_LOCAL_MODEL`           | HuggingFace id for the local embed model             |
| `S3_ENDPOINT_URL`                 | Empty for AWS S3; set to MinIO URL locally           |
| `S3_BUCKET`                       | Object storage bucket name                           |
| `CHUNK_SIZE` / `CHUNK_OVERLAP`    | Chunker token budget                                 |
| `CORS_ORIGINS`                    | JSON array of allowed origins                        |

`.env.example` ships with sane defaults for local Docker.

## Database

Postgres 16 with `pgvector` and `uuid-ossp` extensions. The Compose
service uses the `pgvector/pgvector:pg16` image which has the
extension precompiled. `scripts/db/init.sql` enables both extensions
on first volume creation; Alembic migrations also create them
idempotently for portability.

Migrations:

```bash
make migrate              # apply pending
make migrate-down         # roll back one revision
make migrate-status       # current revision + history
make migrate-new MSG="add foo column"
```

## Production shape (not deployed)

Mapping of local components to AWS:

| Local                  | Production                                                  |
|------------------------|-------------------------------------------------------------|
| Postgres in Docker     | Amazon RDS Postgres (Multi-AZ) with `pgvector` extension    |
| MinIO container        | Amazon S3 bucket with KMS-managed encryption + lifecycle    |
| FastAPI in Docker      | API Gateway + Lambda (low traffic) or ECS Fargate (steady)  |
| Vite dev server        | CloudFront in front of an S3 bucket hosting the SPA build   |
| Sync ingestion in API  | S3 ObjectCreated event → SQS → worker Lambda                |
| (none)                 | Amazon Cognito user pool for JWT auth                       |
| `make smoke`           | CloudWatch alarms on synthetic chat invocations             |
| stdout JSON logs       | CloudWatch Logs + structured metric filters                 |
| (none)                 | AWS WAF in front of CloudFront and API Gateway              |

The codebase is structured so the swap is a single change per surface.
The Bedrock client already targets a real AWS region. The S3 adapter
just drops `endpoint_url` and the AWS credential chain takes over.
The DB connection string changes to RDS. The frontend build emits a
plain static SPA that any CDN can host.

## Tearing down

Local:

```bash
make down                 # stop containers, keep volumes
make clean                # stop containers, remove volumes (wipes db + minio)
```

`make clean` deletes the Postgres volume and the MinIO data volume.
The next `make up` will start with empty state.
