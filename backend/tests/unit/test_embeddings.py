"""Tests for embedding adapters.

Real embedding models are too heavy/slow for unit tests (gigabyte
downloads, multi-second loads). Instead we:
  * verify get_provider() returns the right type for each config setting
  * verify the BedrockEmbeddingProvider parses Titan responses correctly
    via a stubbed client
  * verify shape/dimension validation catches a wrong-size response

The full local model is exercised by the embedding smoke test
(`make embed-smoke`).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from app.adapters.embeddings import (
    BedrockEmbeddingProvider,
    LocalEmbeddingProvider,
    get_provider,
)
from app.core.errors import GenerationError
from app.models import EMBEDDING_DIM


# --- get_provider --------------------------------------------------------


def test_get_provider_returns_local_by_default() -> None:
    get_provider.cache_clear()
    with patch("app.adapters.embeddings.settings") as mock_s:
        mock_s.embedding_provider = "local"
        mock_s.embedding_local_model = "BAAI/bge-large-en-v1.5"
        provider = get_provider()
    assert isinstance(provider, LocalEmbeddingProvider)
    get_provider.cache_clear()


def test_get_provider_returns_bedrock_when_configured() -> None:
    get_provider.cache_clear()
    with patch("app.adapters.embeddings.settings") as mock_s:
        mock_s.embedding_provider = "bedrock"
        mock_s.bedrock_embedding_model_id = "amazon.titan-embed-text-v2:0"
        provider = get_provider()
    assert isinstance(provider, BedrockEmbeddingProvider)
    get_provider.cache_clear()


# --- Bedrock provider with stubbed client --------------------------------


class _StubBedrockBody:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


class _StubBedrockClient:
    def __init__(self, *, dim: int = EMBEDDING_DIM) -> None:
        self.invocations: list[dict[str, Any]] = []
        self._dim = dim

    def invoke_model(self, *, modelId: str, body: str) -> dict[str, Any]:
        self.invocations.append({"modelId": modelId, "body": json.loads(body)})
        return {"body": _StubBedrockBody({"embedding": [0.1] * self._dim})}


@pytest.mark.asyncio
async def test_bedrock_provider_returns_correct_shape() -> None:
    provider = BedrockEmbeddingProvider()
    stub = _StubBedrockClient()
    provider._client = stub  # type: ignore[assignment]

    vectors = await provider.embed_batch(["hello", "world", "again"])

    assert len(vectors) == 3
    assert all(len(v) == EMBEDDING_DIM for v in vectors)
    assert len(stub.invocations) == 3
    assert stub.invocations[0]["body"]["inputText"] == "hello"
    assert stub.invocations[0]["body"]["dimensions"] == EMBEDDING_DIM
    assert stub.invocations[0]["body"]["normalize"] is True


@pytest.mark.asyncio
async def test_bedrock_provider_rejects_wrong_dim() -> None:
    provider = BedrockEmbeddingProvider()
    provider._client = _StubBedrockClient(dim=128)  # type: ignore[assignment]

    with pytest.raises(GenerationError):
        await provider.embed_batch(["mismatch"])


@pytest.mark.asyncio
async def test_embed_empty_batch_returns_empty() -> None:
    bedrock = BedrockEmbeddingProvider()
    bedrock._client = _StubBedrockClient()  # type: ignore[assignment]
    assert await bedrock.embed_batch([]) == []

    local = LocalEmbeddingProvider()
    # Empty input must short-circuit before touching the (slow) model.
    assert await local.embed_batch([]) == []
