"""Seed the running API with the sample documents in sample_docs/.

Behavior:
  1. Lists existing documents
  2. Deletes them all (clean slate)
  3. Uploads each .md file under sample_docs/
  4. Polls until each is `indexed` or `failed`

Run via:
  make eval-seed
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

API_BASE = "http://localhost:8000"
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_docs"
TIMEOUT = httpx.Timeout(60.0)


def main() -> int:
    if not SAMPLE_DIR.exists():
        print(f"FAIL: sample_docs directory not found: {SAMPLE_DIR}")
        return 1

    files = sorted(SAMPLE_DIR.glob("*.md"))
    files = [f for f in files if f.name.lower() != "readme.md"]
    if not files:
        print(f"FAIL: no markdown files found in {SAMPLE_DIR}")
        return 1

    print(f"sample_docs: {SAMPLE_DIR}")
    print(f"to upload:   {[f.name for f in files]}")
    print()

    with httpx.Client(timeout=TIMEOUT) as client:
        # 1. Delete every existing document
        existing = client.get(f"{API_BASE}/api/documents").raise_for_status().json()
        for doc in existing.get("items", []):
            print(f"deleting old: {doc['filename']}")
            client.delete(f"{API_BASE}/api/documents/{doc['id']}").raise_for_status()

        # 2. Upload sample docs
        uploaded: list[str] = []
        for f in files:
            print(f"uploading:   {f.name}")
            content = f.read_bytes()
            resp = client.post(
                f"{API_BASE}/api/documents",
                files={"file": (f.name, content, "text/markdown")},
            )
            if resp.status_code >= 300:
                print(f"  FAIL: {resp.status_code} {resp.text}")
                return 1
            doc = resp.json()
            uploaded.append(doc["id"])
            status = doc.get("status", "?")
            chunks = doc.get("chunk_count", 0)
            print(f"  -> {status}, {chunks} chunks")

        # 3. Sanity poll (ingestion is sync, so this is mostly a no-op)
        for _ in range(10):
            current = client.get(f"{API_BASE}/api/documents").json()
            statuses = {d["filename"]: d["status"] for d in current.get("items", [])}
            if all(s == "indexed" for s in statuses.values()):
                break
            if any(s == "failed" for s in statuses.values()):
                print(f"FAIL: at least one document failed: {statuses}")
                return 1
            time.sleep(1)

    print("\nRESULT: PASS — sample docs indexed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
