"""Eval metrics for the RAG system.

Deliberately simple, deterministic, and free to run — no LLM-as-judge,
no per-question API costs beyond the Bedrock generation under test. The
metrics here are imperfect proxies for "answer quality" but they're
honest, defensible, and cheap to iterate on.

Per-question metrics:
  * answered           — system did not abstain
  * abstained_correctly — for abstention questions only: did it abstain?
  * cited_anything     — answer includes at least one [c_X] citation
  * cited_expected_source — at least one citation maps to expected source
  * keyword_recall     — fraction of expected_keywords present in answer
  * latency_ms

Aggregate metrics: averages over the per-question results, plus a
breakdown by question category (answer vs. abstain).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Sentence the system is trained to use when context is insufficient.
# Matches the abstention sentence baked into prompts/system.py.
ABSTENTION_PHRASES = [
    "i don't have enough information",
    "i do not have enough information",
    "not enough information",
    "no relevant",
    "the indexed documents",
]

CITATION_RE = re.compile(r"\[c_\d+\]")


@dataclass
class GoldenItem:
    """One question from golden_qa.jsonl."""

    id: str
    question: str
    expected_keywords: list[str]
    expected_source: str | None
    expected_to_abstain: bool


@dataclass
class Citation:
    short_id: str
    document_filename: str
    page: int


@dataclass
class QuestionResult:
    """Per-question outcome with computed metrics."""

    item: GoldenItem
    answer: str
    citations: list[Citation]
    latency_ms: int

    # Computed at construction time
    abstained: bool = False
    abstained_correctly: bool = False
    cited_anything: bool = False
    cited_expected_source: bool = False
    keyword_recall: float = 0.0

    def __post_init__(self) -> None:
        ans_low = self.answer.lower().strip()
        self.abstained = any(p in ans_low for p in ABSTENTION_PHRASES)

        if self.item.expected_to_abstain:
            self.abstained_correctly = self.abstained
        else:
            self.abstained_correctly = False  # not applicable; left at False

        self.cited_anything = bool(CITATION_RE.search(self.answer))

        if self.item.expected_source and self.citations:
            self.cited_expected_source = any(
                c.document_filename == self.item.expected_source for c in self.citations
            )
        else:
            self.cited_expected_source = False

        keywords = self.item.expected_keywords
        if keywords:
            hits = sum(1 for kw in keywords if kw.lower() in ans_low)
            self.keyword_recall = hits / len(keywords)
        else:
            self.keyword_recall = 0.0


def load_golden_set(path: str | Path) -> list[GoldenItem]:
    items: list[GoldenItem] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        items.append(
            GoldenItem(
                id=d["id"],
                question=d["question"],
                expected_keywords=d.get("expected_keywords", []),
                expected_source=d.get("expected_source"),
                expected_to_abstain=bool(d.get("expected_to_abstain", False)),
            )
        )
    return items


@dataclass
class AggregateReport:
    """Aggregate metrics over all results."""

    total: int
    answer_questions: int
    abstain_questions: int

    # On answer questions:
    answered_rate: float            # fraction that did NOT abstain
    cited_anything_rate: float
    cited_expected_source_rate: float
    avg_keyword_recall: float

    # On abstention questions:
    abstain_precision: float        # fraction correctly abstained

    # Latency
    p50_latency_ms: int
    p95_latency_ms: int

    by_question: list[dict[str, Any]] = field(default_factory=list)


def aggregate(results: list[QuestionResult]) -> AggregateReport:
    answer_q = [r for r in results if not r.item.expected_to_abstain]
    abstain_q = [r for r in results if r.item.expected_to_abstain]

    answered_rate = (
        sum(1 for r in answer_q if not r.abstained) / len(answer_q)
        if answer_q else 0.0
    )
    cited_anything_rate = (
        sum(1 for r in answer_q if r.cited_anything) / len(answer_q)
        if answer_q else 0.0
    )
    cited_expected_rate = (
        sum(1 for r in answer_q if r.cited_expected_source) / len(answer_q)
        if answer_q else 0.0
    )
    avg_recall = (
        sum(r.keyword_recall for r in answer_q) / len(answer_q)
        if answer_q else 0.0
    )

    abstain_precision = (
        sum(1 for r in abstain_q if r.abstained_correctly) / len(abstain_q)
        if abstain_q else 0.0
    )

    latencies = sorted(r.latency_ms for r in results)
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0

    return AggregateReport(
        total=len(results),
        answer_questions=len(answer_q),
        abstain_questions=len(abstain_q),
        answered_rate=answered_rate,
        cited_anything_rate=cited_anything_rate,
        cited_expected_source_rate=cited_expected_rate,
        avg_keyword_recall=avg_recall,
        abstain_precision=abstain_precision,
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        by_question=[
            {
                "id": r.item.id,
                "question": r.item.question,
                "expected_to_abstain": r.item.expected_to_abstain,
                "abstained": r.abstained,
                "abstained_correctly": r.abstained_correctly,
                "cited_anything": r.cited_anything,
                "cited_expected_source": r.cited_expected_source,
                "keyword_recall": round(r.keyword_recall, 3),
                "latency_ms": r.latency_ms,
                "answer": r.answer,
                "citations": [asdict(c) for c in r.citations],
            }
            for r in results
        ],
    )


def render_markdown(report: AggregateReport, *, title: str = "Eval report") -> str:
    """Format the aggregate report as a readable markdown document."""
    lines: list[str] = []
    add = lines.append

    add(f"# {title}\n")
    add(f"- Total questions: **{report.total}**")
    add(f"- Answer-expected: {report.answer_questions}")
    add(f"- Abstain-expected: {report.abstain_questions}\n")

    add("## Aggregate metrics\n")
    add("### On answer-expected questions")
    add(f"- **Answered rate**: {report.answered_rate:.1%} (system did not abstain when it shouldn't have)")
    add(f"- **Cited anything**: {report.cited_anything_rate:.1%}")
    add(f"- **Cited expected source**: {report.cited_expected_source_rate:.1%}")
    add(f"- **Avg keyword recall**: {report.avg_keyword_recall:.1%}\n")

    add("### On abstention-expected questions")
    add(f"- **Abstain precision**: {report.abstain_precision:.1%} (correctly refused)\n")

    add("### Latency")
    add(f"- p50: **{report.p50_latency_ms} ms**")
    add(f"- p95: **{report.p95_latency_ms} ms**\n")

    add("## Per-question breakdown\n")
    add("| id | type | abstained | cited expected | recall | latency |")
    add("|----|------|-----------|----------------|--------|---------|")
    for q in report.by_question:
        qtype = "abstain" if q["expected_to_abstain"] else "answer"
        ok = "✓" if (
            (q["expected_to_abstain"] and q["abstained_correctly"])
            or (not q["expected_to_abstain"] and q["cited_anything"] and not q["abstained"])
        ) else "·"
        add(
            f"| `{q['id']}` | {qtype} | "
            f"{'yes' if q['abstained'] else 'no'} | "
            f"{ok if q['cited_expected_source'] else '·'} | "
            f"{q['keyword_recall']:.2f} | "
            f"{q['latency_ms']} ms |"
        )

    add("\n## Sample answers\n")
    for q in report.by_question[:5]:
        add(f"### `{q['id']}` — {q['question']}")
        add(f"> {q['answer'].strip() or '(empty)'}\n")

    return "\n".join(lines) + "\n"
