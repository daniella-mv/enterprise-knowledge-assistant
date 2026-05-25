"""Document chunker.

Splits parsed pages into chunks suitable for embedding.

  * RecursiveCharacterTextSplitter from langchain-text-splitters.
    Splits hierarchically on paragraph -> sentence -> word boundaries,
    so chunks rarely break mid-sentence.
  * Token-counted via tiktoken (cl100k_base). Default 800 tokens per
    chunk, 100 token overlap. Tunable in settings.

Each page is chunked independently so source page numbers are preserved
on every resulting chunk. Chunks are not merged across pages.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.services.parser import ParsedPage


@dataclass(frozen=True, slots=True)
class Chunk:
    """One token-bounded slice of a document.

    chunk_index is monotonic across the entire document so storage can
    preserve original ordering at retrieval time.
    """

    chunk_index: int  # 0-indexed within the document
    page: int  # 1-indexed page from the source
    text: str


def chunk_pages(
    pages: list[ParsedPage],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """Split parsed pages into token-counted chunks, preserving page numbers.

    A page that fits in a single chunk produces one Chunk. A page longer
    than chunk_size is split into multiple chunks with the configured
    overlap. Empty/whitespace-only chunks are dropped.
    """
    chunk_size = chunk_size if chunk_size is not None else settings.chunk_size
    chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # Order matters: try paragraph breaks first, then sentence, then word.
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
    )

    chunks: list[Chunk] = []
    chunk_index = 0

    for parsed in pages:
        for piece in splitter.split_text(parsed.text):
            text = piece.strip()
            if not text:
                continue
            chunks.append(Chunk(chunk_index=chunk_index, page=parsed.page, text=text))
            chunk_index += 1

    return chunks
