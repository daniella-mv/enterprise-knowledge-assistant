"""Application settings.

All configuration comes from environment variables (or a local .env file
during development). Settings are validated by pydantic at startup so the
service refuses to boot with a malformed config.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level settings object. Read once at import time as `settings`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    environment: Literal["local", "dev", "prod"] = "local"
    version: str = "0.1.0"
    log_level: str = "INFO"

    # --- HTTP / CORS ---
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # --- Database ---
    database_url: str = "postgresql+psycopg://eka:eka@db:5432/eka"

    # --- AWS / Bedrock ---
    aws_region: str = "us-east-1"
    bedrock_text_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    # --- Chunking ---
    chunk_size: int = 800           # target tokens per chunk
    chunk_overlap: int = 100        # token overlap between adjacent chunks

    # --- Embeddings ---
    # "local"   -> fastembed + BAAI/bge-large-en-v1.5 (free, runs on CPU)
    # "bedrock" -> Amazon Titan Text Embeddings v2 (paid; needs AWS creds)
    embedding_provider: Literal["local", "bedrock"] = "local"
    embedding_local_model: str = "BAAI/bge-large-en-v1.5"

    # --- Object storage (S3 / MinIO) ---
    # Leave s3_endpoint_url empty (or unset) to use real AWS S3 with the
    # standard credential chain. Set it to a MinIO URL for local dev.
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = "eka-documents"


settings = Settings()
