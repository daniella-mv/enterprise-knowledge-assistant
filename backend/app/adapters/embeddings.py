"""Embedding model adapter.

Two backends behind one async interface, selected by
settings.embedding_provider:

  - "local"   fastembed (ONNX) + BAAI/bge-large-en-v1.5
              1024-dim vectors, runs on CPU, no external calls.
  - "bedrock" Amazon Titan Text Embeddings v2
              1024-dim vectors via Bedrock runtime.

Both produce L2-normalized 1024-dim vectors compatible with the
pgvector column and the HNSW vector_cosine_ops index.

Local notes:
  - The fastembed model lazy-loads on first use (~1.3GB download cached
    under ~/.cache/fastembed). docker-compose mounts that path as a
    named volume so the model survives container restarts.
  - fastembed is synchronous; we wrap calls in asyncio.to_thread.

Bedrock notes:
  - Titan accepts one text per request; we parallelize across an
    asyncio thread pool.
  - `dimensions: 1024` and `normalize: true` keep vectors compatible
    with the local provider.
"""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from app.config import settings
from app.core.errors import GenerationError
from app.core.logging import get_logger
from app.models import EMBEDDING_DIM

logger = get_logger(__name__)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Async interface implemented by every embedding backend."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbeddingProvider:
    """fastembed-backed embeddings (no AWS, no internet at runtime)."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_local_model
        self._model: Any | None = None  # fastembed.TextEmbedding, lazy

    def _ensure_model(self) -> Any:
        if self._model is None:
            from fastembed import TextEmbedding

            logger.info("loading_local_embedding_model", model=self.model_name)
            self._model = TextEmbedding(self.model_name)
        return self._model

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model()

        def _embed() -> list[list[float]]:
            return [vec.tolist() for vec in model.embed(texts)]

        vectors = await asyncio.to_thread(_embed)
        for i, v in enumerate(vectors):
            if len(v) != EMBEDDING_DIM:
                raise GenerationError(
                    f"local embedding dim mismatch on item {i}: "
                    f"expected {EMBEDDING_DIM}, got {len(v)}"
                )
        return vectors


class BedrockEmbeddingProvider:
    """Amazon Titan v2 embeddings via Bedrock runtime."""

    def __init__(self, model_id: str | None = None) -> None:
        self.model_id = model_id or settings.bedrock_embedding_model_id
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        return self._client

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._ensure_client()

        def _embed_one(text: str) -> list[float]:
            body = json.dumps(
                {
                    "inputText": text,
                    "dimensions": EMBEDDING_DIM,
                    "normalize": True,
                }
            )
            try:
                resp = client.invoke_model(modelId=self.model_id, body=body)
                payload = json.loads(resp["body"].read())
                vec = payload["embedding"]
                if len(vec) != EMBEDDING_DIM:
                    raise GenerationError(
                        f"bedrock returned {len(vec)} dims; expected {EMBEDDING_DIM}"
                    )
                return vec
            except GenerationError:
                raise
            except Exception as e:  # noqa: BLE001 - boto3 error variety
                raise GenerationError(f"bedrock embed_one failed: {e}") from e

        return await asyncio.gather(*[asyncio.to_thread(_embed_one, t) for t in texts])


@lru_cache(maxsize=1)
def get_provider() -> EmbeddingProvider:
    """Singleton provider per process. Selected by EMBEDDING_PROVIDER."""
    if settings.embedding_provider == "bedrock":
        logger.info("embedding_provider_selected", provider="bedrock")
        return BedrockEmbeddingProvider()
    logger.info("embedding_provider_selected", provider="local")
    return LocalEmbeddingProvider()
