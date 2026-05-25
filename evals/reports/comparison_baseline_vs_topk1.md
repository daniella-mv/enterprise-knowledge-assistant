# Eval comparison — baseline vs `top_k=1`

A simple tuning experiment to test whether reducing retrieval breadth
hurts answer quality on the 20-question golden set.

## Setup

- **Corpus**: `sample_docs/` (employee handbook, security policy, helpdesk SOP)
- **Embeddings**: `BAAI/bge-large-en-v1.5` via fastembed (local)
- **LLM**: Anthropic Claude Haiku 4.5 on Bedrock
- **Retrieval**: hybrid (vector kNN + BM25 with RRF fusion)
- **Variable**: `top_k` passed to `/api/chat` — 5 (default) vs 1

## Results

| Metric                          | top_k=5 (baseline) | top_k=1 | Δ        |
|---------------------------------|--------------------|---------|----------|
| Answered rate (non-abstain)     | 100.0%             | 100.0%  | —        |
| Cited anything                  | 100.0%             | 100.0%  | —        |
| Cited expected source           | 100.0%             | 100.0%  | —        |
| Avg keyword recall              | 97.8%              | 96.1%   | −1.7 pp  |
| Abstain precision               | 100.0%             | 100.0%  | —        |
| Latency p50                     | 1245 ms            | 1337 ms | +7%      |
| Latency p95                     | 2014 ms            | 10491 ms| +5.2x    |

## Interpretation

1. **Citation accuracy was unaffected.** On a small, well-separated corpus,
   the single closest chunk was always from the correct document. We cannot
   conclude this would hold on a larger or more topically overlapping corpus.

2. **Keyword recall dropped slightly (−1.7 pp).** Multi-fact questions
   (e.g. ticket lifecycle stages) have answers that live in fewer chunks
   than a 5-chunk context window — losing those extra chunks cost some
   detail.

3. **Latency tail got dramatically worse (p95 5.2x).** This is almost
   certainly an outlier (likely a single slow Bedrock invocation rather
   than a systemic effect; p50 was nearly unchanged). Worth re-running
   to verify; not a basis for a tuning decision on its own.

## Decision

Keep `top_k=5` as the default. The recall improvement is small but
free — Bedrock cost scales with prompt tokens, and 5 chunks of ~400
tokens each is well within Haiku's input budget.

## What this experiment **does not** prove

- That top_k=5 is optimal vs. top_k=10 or top_k=3.
- That hybrid retrieval beats pure vector on this corpus (would need a
  separate experiment).
- That these results generalize to corpora with more topical overlap
  or 100x more documents.

These are all good follow-up experiments — the eval harness handles them
with one command each.
