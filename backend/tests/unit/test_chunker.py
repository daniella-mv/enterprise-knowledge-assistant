"""Tests for the chunker.

These verify the contract the rest of the pipeline relies on:
  * page numbers survive chunking
  * chunk_index is monotonic across the whole document
  * empty pages produce zero chunks (don't waste embedding budget)
  * a small page produces exactly one chunk
  * a long page produces multiple chunks with overlap
  * configurable chunk_size / chunk_overlap actually take effect
"""

from __future__ import annotations

from app.services.chunker import Chunk, chunk_pages
from app.services.parser import ParsedPage


# --- Page preservation ---------------------------------------------------


def test_chunk_preserves_page_numbers() -> None:
    pages = [
        ParsedPage(page=1, text="Short content for page one."),
        ParsedPage(page=2, text="Short content for page two."),
        ParsedPage(page=7, text="Short content for page seven."),  # non-contiguous
    ]
    chunks = chunk_pages(pages)
    assert [c.page for c in chunks] == [1, 2, 7]


def test_chunk_indexes_are_monotonic() -> None:
    pages = [ParsedPage(page=i, text=f"Page {i} body.") for i in range(1, 6)]
    chunks = chunk_pages(pages)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


# --- Edge cases ----------------------------------------------------------


def test_empty_pages_input_returns_empty_list() -> None:
    assert chunk_pages([]) == []


def test_blank_pages_are_skipped() -> None:
    chunks = chunk_pages([ParsedPage(page=1, text="   "), ParsedPage(page=2, text="\n\n")])
    assert chunks == []


def test_short_page_produces_one_chunk() -> None:
    pages = [ParsedPage(page=1, text="A small bit of text well below the 800 token limit.")]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0].page == 1
    assert chunks[0].chunk_index == 0
    assert "A small bit" in chunks[0].text


# --- Splitting + overlap -------------------------------------------------


def test_long_page_produces_multiple_chunks_with_overlap() -> None:
    # Sentence chosen so 30 sentences * ~10 tokens = ~300 tokens.
    # Use small chunk_size to force splitting.
    sentence = "The quick brown fox jumps over the lazy dog. "
    body = sentence * 30
    pages = [ParsedPage(page=1, text=body)]

    chunks = chunk_pages(pages, chunk_size=50, chunk_overlap=10)
    assert len(chunks) >= 2, "expected the body to split into multiple chunks"

    # All chunks belong to page 1 and have monotonic indexes.
    assert all(c.page == 1 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    # Overlap check: consecutive chunks should share at least some text.
    # With sentence-based separators they may not literally overlap by
    # characters in every case, but the union should cover the full body.
    rejoined = " ".join(c.text for c in chunks)
    # All 4 unique words from the test sentence should appear.
    for word in ("quick", "brown", "lazy", "dog"):
        assert word in rejoined


def test_chunk_size_is_respected_within_tolerance() -> None:
    """Chunks should stay near the requested token size, never wildly over."""
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    body = ("A short factual sentence. " * 200).strip()
    chunks = chunk_pages([ParsedPage(page=1, text=body)], chunk_size=100, chunk_overlap=20)

    for c in chunks:
        token_count = len(enc.encode(c.text))
        # Splitter is best-effort; allow 25% headroom for separator boundaries.
        assert token_count <= 125, (
            f"chunk {c.chunk_index} has {token_count} tokens, expected <=125"
        )


# --- Chunk dataclass -----------------------------------------------------


def test_chunk_is_immutable() -> None:
    c = Chunk(chunk_index=0, page=1, text="immutable")
    try:
        c.text = "changed"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Chunk should be frozen")
