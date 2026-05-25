"""End-to-end chat smoke test.

Posts a question to /api/chat over the running API and prints the streaming
answer + citations as they arrive. Verifies the entire RAG path:
  retrieval -> prompt -> Bedrock streaming -> citation enrichment.

Run via:
  make chat-smoke
or:
  docker compose exec api uv run python scripts/chat_smoke_test.py "your question"

If you have no documents indexed yet, upload one first via:
  curl -X POST -F "file=@/tmp/handbook.txt" http://localhost:8000/api/documents
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402


DEFAULT_QUESTION = "What is the PTO policy?"


def main() -> int:
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else DEFAULT_QUESTION
    print(f"Q: {question}\n")
    print("A: ", end="", flush=True)

    citations: list[dict] = []
    error_msg: str | None = None

    payload = {"message": question, "top_k": 5}
    try:
        with httpx.stream(
            "POST",
            "http://localhost:8000/api/chat",
            json=payload,
            timeout=60.0,
        ) as r:
            if r.status_code != 200:
                print(f"\nHTTP {r.status_code}: {r.read().decode()}")
                return 1

            event = None
            for line in r.iter_lines():
                if not line:
                    event = None
                    continue
                if line.startswith("event:"):
                    event = line.removeprefix("event:").strip()
                elif line.startswith("data:"):
                    data = line.removeprefix("data:").strip()
                    if event == "token":
                        print(data, end="", flush=True)
                    elif event == "done":
                        citations = json.loads(data).get("citations", [])
                    elif event == "error":
                        error_msg = json.loads(data).get("message", data)
    except httpx.HTTPError as e:
        print(f"\nrequest failed: {e}")
        return 1

    print()  # newline after answer
    if error_msg:
        print(f"\nERROR: {error_msg}")
        return 1

    print(f"\n--- Citations ({len(citations)}) ---")
    for c in citations:
        snippet = c["snippet"][:100].replace("\n", " ")
        print(f"  [{c['short_id']}] {c['document_filename']} p.{c['page']}: {snippet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
