"""Unit tests for generation: prompt building + citation extraction."""

from __future__ import annotations

from uuid import uuid4

from app.services.generation import (
    build_rag_prompt,
    extract_cited_ids,
)
from app.services.retrieval import RetrievedChunk


def _chunk(text: str, *, filename: str = "doc.pdf", page: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        id=uuid4(),
        document_id=uuid4(),
        document_filename=filename,
        chunk_index=0,
        page=page,
        text=text,
        score=1.0,
    )


# --- build_rag_prompt ----------------------------------------------------


def test_build_prompt_assigns_short_ids_in_order() -> None:
    chunks = [_chunk("alpha"), _chunk("beta"), _chunk("gamma")]
    msg, cmap = build_rag_prompt("What is alpha?", chunks)

    assert "c_0" in cmap.short_to_chunk
    assert "c_1" in cmap.short_to_chunk
    assert "c_2" in cmap.short_to_chunk
    assert cmap.short_to_chunk["c_0"].text == "alpha"
    assert cmap.short_to_chunk["c_2"].text == "gamma"
    assert "Question: What is alpha?" in msg
    assert '<context id="c_0"' in msg


def test_build_prompt_includes_filename_and_page() -> None:
    chunks = [_chunk("hello", filename="handbook.pdf", page=7)]
    msg, _ = build_rag_prompt("hi", chunks)
    assert 'source="handbook.pdf"' in msg
    assert 'page="7"' in msg


def test_build_prompt_with_no_chunks_signals_no_context() -> None:
    msg, cmap = build_rag_prompt("anything?", [])
    assert "(no relevant passages found)" in msg
    assert "Question: anything?" in msg
    assert cmap.short_to_chunk == {}


# --- extract_cited_ids ---------------------------------------------------


def test_extract_finds_single_citation() -> None:
    assert extract_cited_ids("PTO is 15 days [c_3].") == ["c_3"]


def test_extract_finds_multiple_in_order() -> None:
    text = "Health is fully paid [c_0]. Dental is 50% [c_2]. PTO is 15 [c_1]."
    assert extract_cited_ids(text) == ["c_0", "c_2", "c_1"]


def test_extract_dedupes_repeated_citations() -> None:
    text = "Per [c_5], yes. As [c_5] also notes [c_2], confirmed."
    assert extract_cited_ids(text) == ["c_5", "c_2"]


def test_extract_handles_adjacent_citations() -> None:
    text = "Both sources agree [c_0][c_1]."
    assert extract_cited_ids(text) == ["c_0", "c_1"]


def test_extract_returns_empty_when_no_citations() -> None:
    assert extract_cited_ids("I don't know.") == []


def test_extract_ignores_malformed_brackets() -> None:
    # [c_X] is invalid (non-digit), [42] missing prefix, [c_] missing digit
    text = "Bad: [c_X] [42] [c_] but [c_9] is fine."
    assert extract_cited_ids(text) == ["c_9"]
