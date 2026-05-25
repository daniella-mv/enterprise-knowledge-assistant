"""Tests for the document parser.

Covers:
  - format detection from MIME and filename extension
  - PDF page-number preservation
  - DOCX paragraph + table extraction
  - UTF-8 / non-UTF-8 text handling
  - error paths (unsupported format, encrypted PDF)
"""

from __future__ import annotations

import io

import pytest

from app.core.errors import IngestionError
from app.services import parser
from app.services.parser import ParsedPage


# --- Format detection ----------------------------------------------------


def test_detect_format_prefers_mime_over_extension() -> None:
    fmt = parser._detect_format("noext", "application/pdf")
    assert fmt == "pdf"


def test_detect_format_strips_charset() -> None:
    fmt = parser._detect_format("readme.md", "text/markdown; charset=utf-8")
    assert fmt == "md"


def test_detect_format_falls_back_to_extension() -> None:
    fmt = parser._detect_format("policy.docx", None)
    assert fmt == "docx"


def test_detect_format_falls_back_when_mime_unknown() -> None:
    # Browsers often send octet-stream for less common types.
    fmt = parser._detect_format("policy.docx", "application/octet-stream")
    assert fmt == "docx"


def test_detect_format_unsupported_raises() -> None:
    with pytest.raises(IngestionError) as ei:
        parser._detect_format("image.png", "image/png")
    assert ei.value.code == "unsupported_format"


# --- Plain text ----------------------------------------------------------


def test_parse_txt_returns_one_page(sample_txt: tuple[str, bytes]) -> None:
    filename, content = sample_txt
    pages = parser.parse(filename, content)
    assert len(pages) == 1
    assert pages[0].page == 1
    assert "PTO" in pages[0].text


def test_parse_md_returns_one_page(sample_md: tuple[str, bytes]) -> None:
    filename, content = sample_md
    pages = parser.parse(filename, content, content_type="text/markdown")
    assert len(pages) == 1
    assert pages[0].page == 1
    assert "Information Security" in pages[0].text
    assert "MFA" in pages[0].text


def test_parse_text_handles_non_utf8() -> None:
    # latin-1 encoded "Caf\xe9" (Café) — would fail strict UTF-8 decoding.
    content = "Café opens at 9 a.m.".encode("latin-1")
    pages = parser.parse("notes.txt", content)
    assert len(pages) == 1
    # The replacement character may appear, but the surrounding text survives.
    assert "opens at 9 a.m." in pages[0].text


def test_parse_empty_text_returns_empty_list() -> None:
    pages = parser.parse("empty.txt", b"   \n  \n  ")
    assert pages == []


# --- DOCX ----------------------------------------------------------------


def test_parse_docx_extracts_paragraphs_and_tables(
    sample_docx: tuple[str, bytes],
) -> None:
    filename, content = sample_docx
    pages = parser.parse(filename, content)
    assert len(pages) == 1, "DOCX collapses to a single page"
    text = pages[0].text
    assert "IT Helpdesk SOP" in text
    assert "triaged within one business hour" in text
    # Table cell content is included.
    assert "Severity" in text
    assert "15 minutes" in text


def test_parse_docx_invalid_bytes_raises() -> None:
    with pytest.raises(IngestionError) as ei:
        parser.parse("broken.docx", b"this is not really a docx file")
    assert ei.value.code == "docx_invalid"


# --- PDF -----------------------------------------------------------------


def test_parse_pdf_preserves_page_numbers(
    sample_pdf_two_pages: tuple[str, bytes],
) -> None:
    filename, content = sample_pdf_two_pages
    pages = parser.parse(filename, content)
    # We wrote two pages; both should come back with their numbers intact.
    assert len(pages) == 2
    assert pages[0].page == 1
    assert pages[1].page == 2

    page1_text = pages[0].text
    page2_text = pages[1].text
    assert "Employee Benefits Summary" in page1_text
    assert "Retirement Plans" in page2_text
    # The 401(k) line is on page 2, not page 1.
    assert "401(k)" not in page1_text
    assert "401(k)" in page2_text


def test_parse_pdf_invalid_bytes_raises() -> None:
    with pytest.raises(IngestionError) as ei:
        parser.parse("fake.pdf", b"%PDF-1.4 garbage that is not a real PDF")
    assert ei.value.code == "pdf_invalid"


# --- ParsedPage ---------------------------------------------------------


def test_parsed_page_is_immutable() -> None:
    p = ParsedPage(page=1, text="hello")
    with pytest.raises(Exception):
        p.text = "changed"  # type: ignore[misc]
