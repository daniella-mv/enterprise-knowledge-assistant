"""Embedding smoke test.

Loads the configured embedding provider and verifies it produces
1024-dim normalized vectors. For the local provider this triggers the
one-time fastembed model download (~1.3GB) on first run; subsequent
runs use the cached model and complete in under a second.

Run via:
  make embed-smoke
or:
  docker compose exec api uv run python scripts/embedding_smoke_test.py
"""

from __future__ import annotations

import asyncio
import math
import sys
import time
from pathlib import Path

# Allow running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.embeddings import get_provider  # noqa: E402
from app.config import settings  # noqa: E402
from app.models import EMBEDDING_DIM  # noqa: E402


SAMPLE_TEXTS = [
    "Employees are entitled to fifteen PTO days per year.",
    "Multi-factor authentication is required for production access.",
    "401(k) matching is up to four percent of base salary.",
]


async def main() -> int:
    print(f"provider:    {settings.embedding_provider}")
    if settings.embedding_provider == "local":
        print(f"model:       {settings.embedding_local_model}")
    else:
        print(f"model:       {settings.bedrock_embedding_model_id}")
    print(f"target dim:  {EMBEDDING_DIM}")
    print()

    provider = get_provider()

    print(f"Embedding {len(SAMPLE_TEXTS)} short texts...")
    if settings.embedding_provider == "local":
        print("(first run downloads ~1.3GB; subsequent runs are instant)")
    print()

    start = time.perf_counter()
    try:
        vectors = await provider.embed_batch(SAMPLE_TEXTS)
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1
    elapsed = time.perf_counter() - start

    if len(vectors) != len(SAMPLE_TEXTS):
        print(f"FAIL: expected {len(SAMPLE_TEXTS)} vectors, got {len(vectors)}")
        return 1

    for i, vec in enumerate(vectors):
        if len(vec) != EMBEDDING_DIM:
            print(f"FAIL: vector {i} has dim {len(vec)}, expected {EMBEDDING_DIM}")
            return 1

    # Sanity: vectors should be approximately L2-normalized (norm ~= 1).
    for i, vec in enumerate(vectors):
        norm = math.sqrt(sum(x * x for x in vec))
        if not (0.85 <= norm <= 1.15):
            print(f"WARN: vector {i} L2 norm = {norm:.3f} (expected ~1.0 for normalized embeddings)")

    print(f"[OK] returned {len(vectors)} vectors of {EMBEDDING_DIM} dims")
    print(f"[OK] elapsed: {elapsed:.2f}s")
    print(f"[OK] first vector preview: [{vectors[0][0]:.4f}, {vectors[0][1]:.4f}, {vectors[0][2]:.4f}, ...]")
    print()
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
