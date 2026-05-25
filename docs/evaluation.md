# Evaluation

The system ships with an evaluation harness so any change to retrieval,
prompts, chunking, or models produces measured before/after numbers
instead of vibes.

## Methodology

A 20-question golden set hand-written against the three sample
documents in `sample_docs/`. Half the questions are factual lookups
where the expected behavior is to answer correctly with a citation to
the right source. Half are out-of-scope questions where the expected
behavior is to abstain explicitly with the configured abstention
sentence.

For each question, the harness:

1. POSTs the question to the live `/api/chat` endpoint
2. Consumes the SSE stream — accumulates the answer text and the final
   citation list
3. Computes per-question metrics
4. Aggregates across the set

The harness lives in `evals/` and runs inside the API container so it
shares the container's network and configuration:

```bash
make eval-seed                # wipes documents, uploads sample_docs/
make eval LABEL=baseline      # runs all 20 questions, writes a report
make eval LABEL=topk1 TOPK=1  # tuning experiment
```

Each run produces three artifacts under `evals/reports/`:

- `<timestamp>_<label>.md` — full markdown report (per-question table + sample answers)
- `<timestamp>_<label>.json` — the same data as JSON for downstream tooling
- `latest.md` — overwritten on each run for quick reference

## Metrics

For *answer-expected* questions:

| Metric                      | Definition                                                   |
|-----------------------------|--------------------------------------------------------------|
| Answered rate               | Fraction that did NOT abstain                                |
| Cited anything              | Fraction whose answer contains at least one `[c_<n>]` marker |
| Cited expected source       | Fraction whose citations include the question's expected source filename |
| Avg keyword recall          | Average across questions: fraction of `expected_keywords` present in the answer |

For *abstention-expected* questions:

| Metric                | Definition                                                   |
|-----------------------|--------------------------------------------------------------|
| Abstain precision     | Fraction that contained one of the abstention phrases        |

Latency: p50 and p95 across all questions, measured from POST to the
last SSE event of each response.

These are deliberately simple metrics. They don't require an LLM-as-judge
(which adds cost and a circular-reasoning risk) and they're
deterministic — re-running the same configuration produces identical
numbers up to Bedrock's response variance.

## Baseline results

Configuration:

- Corpus: three sample documents (handbook, security policy, helpdesk SOP)
- Chunking: 800 tokens, 100 overlap
- Embeddings: `BAAI/bge-large-en-v1.5` via fastembed
- Retrieval: hybrid (vector kNN + tsvector ts_rank), RRF fusion, top_k=5
- LLM: Anthropic Claude Haiku 4.5 on Bedrock, temperature 0.1

Numbers from the most recent baseline run:

| Metric                      | Result   |
|-----------------------------|----------|
| Answered rate               | 100.0%   |
| Cited anything              | 100.0%   |
| Cited expected source       | 100.0%   |
| Avg keyword recall          | 97.8%    |
| Abstain precision           | 100.0%   |
| Latency p50                 | 1245 ms  |
| Latency p95                 | 2014 ms  |

## Tuning experiment: top_k=5 vs top_k=1

Detailed comparison in
[`evals/reports/comparison_baseline_vs_topk1.md`](../evals/reports/comparison_baseline_vs_topk1.md).
Headline:

| Metric                | top_k=5 | top_k=1 | Δ        |
|-----------------------|---------|---------|----------|
| Cited expected source | 100.0%  | 100.0%  | —        |
| Avg keyword recall    | 97.8%   | 96.1%   | −1.7 pp  |
| Abstain precision     | 100.0%  | 100.0%  | —        |
| Latency p95           | 2014 ms | 10491 ms| +5.2x    |

Citation accuracy held because the single closest chunk was always
from the right document on this small, topically-separated corpus.
Keyword recall dropped slightly on multi-fact questions where the full
answer needs information spread across chunks. The latency p95 jump
appears to be an outlier rather than a systemic effect (p50 was nearly
unchanged); a re-run would clarify.

## Honest caveats

- Metrics are proxies, not ground truth. *Cited expected source* says
  the system included the right document in citations; it does not
  prove the *content* of the answer is faithful to that source.
  Adding LLM-as-judge faithfulness scoring (RAGAS-style) is a clean
  next step.
- The corpus is three documents totaling ~1,500 tokens. Strong scores
  here don't predict behavior on a 10,000-document corpus with
  topical overlap.
- The 5 abstention questions are *clearly* out-of-scope (e.g., "What's
  the company stock ticker?"). A harder eval would include borderline
  cases — questions about topics the corpus alludes to but doesn't
  fully cover.
- Latency is measured against Bedrock's on-demand endpoint from a
  single client; production p95 depends on traffic mixing and
  concurrency limits.

## Repeatability

The harness is deterministic in everything except Bedrock generation
itself. Two consecutive runs differ only in token-level word choice
from Claude — the metrics that matter (citation correctness,
abstention precision, keyword recall) are stable.

To reproduce the baseline:

```bash
make eval-seed
make eval LABEL=baseline
```
