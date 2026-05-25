"""Run the golden Q&A set against the live API and write a markdown report.

Reads questions from `evals/datasets/golden_qa.jsonl`, posts each one to
the chat endpoint as SSE, collects the streamed answer and citations,
computes per-question and aggregate metrics, and writes to
`evals/reports/<timestamp>.md` plus a stable `latest.md`.

Run via:
  make eval                                  # default 20-question set
  docker compose exec api uv run python evals/run_eval.py --label baseline

Pass --label <name> to tag the report file (e.g., "baseline", "k=10",
"chunk-400") so before/after comparisons are easy to keep straight.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Make the package importable when this file is run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.eval_lib import (  # noqa: E402
    Citation,
    GoldenItem,
    QuestionResult,
    aggregate,
    load_golden_set,
    render_markdown,
)

API_BASE = "http://localhost:8000"
GOLDEN_PATH = Path(__file__).resolve().parent / "datasets" / "golden_qa.jsonl"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
TIMEOUT = httpx.Timeout(120.0)


def _ask(client: httpx.Client, item: GoldenItem, top_k: int) -> QuestionResult:
    """Ask one question, consume the SSE stream, return a QuestionResult."""
    started = time.perf_counter()
    answer_parts: list[str] = []
    citations_raw: list[dict] = []

    with client.stream(
        "POST",
        f"{API_BASE}/api/chat",
        json={"message": item.question, "top_k": top_k},
    ) as resp:
        if resp.status_code != 200:
            elapsed = int((time.perf_counter() - started) * 1000)
            return QuestionResult(
                item=item,
                answer=f"<error HTTP {resp.status_code}>",
                citations=[],
                latency_ms=elapsed,
            )

        event: str | None = None
        for line in resp.iter_lines():
            if not line:
                event = None
                continue
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                # Per SSE spec, strip ONE leading space
                raw = line.removeprefix("data:")
                if raw.startswith(" "):
                    raw = raw[1:]
                if event == "token":
                    answer_parts.append(raw)
                elif event == "done":
                    try:
                        payload = json.loads(raw)
                        citations_raw = payload.get("citations", [])
                    except json.JSONDecodeError:
                        pass
                elif event == "error":
                    answer_parts.append(f"<bedrock error: {raw}>")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    citations = [
        Citation(
            short_id=c["short_id"],
            document_filename=c["document_filename"],
            page=c["page"],
        )
        for c in citations_raw
    ]
    return QuestionResult(
        item=item,
        answer="".join(answer_parts),
        citations=citations,
        latency_ms=elapsed_ms,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the RAG eval")
    parser.add_argument(
        "--label",
        default="baseline",
        help="Short tag included in the report filename and title.",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Optional cap on number of questions (for quick smoke runs).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Retrieval top_k passed to /api/chat. Default 5.",
    )
    args = parser.parse_args()

    items = load_golden_set(GOLDEN_PATH)
    if args.max is not None:
        items = items[: args.max]

    print(f"Loaded {len(items)} questions from {GOLDEN_PATH.name}")
    print(f"Hitting API at {API_BASE}")
    print(f"top_k = {args.top_k}\n")

    REPORTS_DIR.mkdir(exist_ok=True)
    results: list[QuestionResult] = []

    with httpx.Client(timeout=TIMEOUT) as client:
        for i, item in enumerate(items, 1):
            print(f"[{i:2}/{len(items)}] {item.id} — {item.question[:60]}")
            try:
                r = _ask(client, item, top_k=args.top_k)
                results.append(r)
                hint = (
                    "✓abstain" if (item.expected_to_abstain and r.abstained_correctly)
                    else "✓answer" if (not item.expected_to_abstain and r.cited_anything and not r.abstained)
                    else "·"
                )
                print(f"           {hint}  {r.latency_ms} ms")
            except Exception as e:
                print(f"           FAIL: {e}")

    report = aggregate(results)

    # Write timestamped + 'latest' files
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    title = f"Eval report — {args.label} ({ts})"
    md = render_markdown(report, title=title)
    timestamped = REPORTS_DIR / f"{ts}_{args.label}.md"
    latest = REPORTS_DIR / "latest.md"
    json_path = REPORTS_DIR / f"{ts}_{args.label}.json"
    timestamped.write_text(md, encoding="utf-8")
    latest.write_text(md, encoding="utf-8")
    json_path.write_text(
        json.dumps(report.__dict__, default=str, indent=2),
        encoding="utf-8",
    )

    print(f"\nReport: {timestamped}")
    print(f"Latest: {latest}\n")

    print("=== Summary ===")
    print(f"  Answered rate (non-abstain Qs):       {report.answered_rate:.1%}")
    print(f"  Cited anything (non-abstain Qs):      {report.cited_anything_rate:.1%}")
    print(f"  Cited expected source:                {report.cited_expected_source_rate:.1%}")
    print(f"  Avg keyword recall:                   {report.avg_keyword_recall:.1%}")
    print(f"  Abstain precision:                    {report.abstain_precision:.1%}")
    print(f"  Latency p50/p95:                      {report.p50_latency_ms} / {report.p95_latency_ms} ms")

    return 0


if __name__ == "__main__":
    sys.exit(main())
