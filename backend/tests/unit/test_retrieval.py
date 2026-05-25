"""Unit tests for retrieval — RRF math, no DB needed."""

from __future__ import annotations

from uuid import uuid4

from app.services.retrieval import reciprocal_rank_fuse


def test_rrf_empty_inputs_returns_empty() -> None:
    assert reciprocal_rank_fuse([]) == {}
    assert reciprocal_rank_fuse([[]]) == {}
    assert reciprocal_rank_fuse([[], []]) == {}


def test_rrf_single_list_ranks_by_position() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    scores = reciprocal_rank_fuse([[a, b, c]], k=60)
    # Score = 1 / (60 + rank). Higher rank = lower score.
    assert scores[a] > scores[b] > scores[c]


def test_rrf_double_appearance_scores_higher_than_single() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    # `a` appears in both; b and c appear in only one each at rank 1.
    scores = reciprocal_rank_fuse([[a, b], [a, c]], k=60)
    assert scores[a] > scores[b]
    assert scores[a] > scores[c]
    # b and c both at rank 1 in their single list -> equal scores.
    assert scores[b] == scores[c]


def test_rrf_k_dampens_low_ranks() -> None:
    a, b = uuid4(), uuid4()
    # Same lists, larger k -> scores closer together.
    small_k = reciprocal_rank_fuse([[a, b]], k=1)
    big_k = reciprocal_rank_fuse([[a, b]], k=1000)
    small_ratio = small_k[a] / small_k[b]
    big_ratio = big_k[a] / big_k[b]
    assert small_ratio > big_ratio  # smaller k = sharper preference


def test_rrf_handles_three_lists() -> None:
    a, b = uuid4(), uuid4()
    scores = reciprocal_rank_fuse([[a, b], [a], [b]], k=60)
    # `a` is at rank 1 in two lists; `b` at rank 2 in one + rank 1 in one.
    # Score(a) = 2/(60+1) = 2/61
    # Score(b) = 1/(60+2) + 1/(60+1) = 1/62 + 1/61
    expected_a = 2.0 / 61
    expected_b = 1.0 / 62 + 1.0 / 61
    assert abs(scores[a] - expected_a) < 1e-9
    assert abs(scores[b] - expected_b) < 1e-9
