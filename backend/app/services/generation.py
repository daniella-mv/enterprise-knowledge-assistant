"""RAG generation: build the prompt, stream the answer, surface citations.

Flow:
  1. caller retrieves chunks via retrieval.hybrid_search
  2. build_rag_prompt wraps each chunk in <context id="c_<n>"> ...
  3. stream_answer streams tokens from Bedrock
  4. caller parses [c_<n>] markers in the final text and maps them back
     to the originating chunks for the citation panel

short IDs (c_0, c_1, ...) are used in place of UUIDs so the model can
reproduce them reliably; the prompt-time index does the lookup.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.adapters.bedrock import stream_chat
from app.prompts.system import SYSTEM_PROMPT
from app.services.retrieval import RetrievedChunk

# Match [c_42] or [c_3][c_7] anywhere in the streamed answer.
CITATION_PATTERN = re.compile(r"\[(c_\d+)\]")


@dataclass(frozen=True, slots=True)
class CitationMap:
    """Maps short citation IDs (c_0, c_1...) to retrieved chunks."""

    short_to_chunk: dict[str, RetrievedChunk]

    def resolve(self, short_id: str) -> RetrievedChunk | None:
        return self.short_to_chunk.get(short_id)


def build_rag_prompt(
    user_question: str, chunks: list[RetrievedChunk]
) -> tuple[str, CitationMap]:
    """Wrap context blocks with citation IDs the model can reproduce.

    Returns (user_message, citation_map). The system prompt is constant
    and provided separately to Bedrock.
    """
    if not chunks:
        # No context -> let the model produce the abstention sentence.
        return (
            f"<context>(no relevant passages found)</context>\n\nQuestion: {user_question}",
            CitationMap(short_to_chunk={}),
        )

    short_to_chunk: dict[str, RetrievedChunk] = {}
    blocks: list[str] = []
    for i, chunk in enumerate(chunks):
        short_id = f"c_{i}"
        short_to_chunk[short_id] = chunk
        blocks.append(
            f'<context id="{short_id}" source="{chunk.document_filename}" page="{chunk.page}">\n'
            f"{chunk.text}\n"
            f"</context>"
        )

    user_message = "\n\n".join(blocks) + f"\n\nQuestion: {user_question}"
    return user_message, CitationMap(short_to_chunk=short_to_chunk)


def extract_cited_ids(answer_text: str) -> list[str]:
    """Return short_ids in first-appearance order, deduplicated."""
    seen: dict[str, None] = {}
    for match in CITATION_PATTERN.finditer(answer_text):
        seen.setdefault(match.group(1), None)
    return list(seen.keys())


async def stream_answer(
    user_question: str,
    chunks: list[RetrievedChunk],
    *,
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> AsyncIterator[str]:
    """Yield Claude's token deltas as they arrive."""
    user_message, _ = build_rag_prompt(user_question, chunks)
    async for delta in stream_chat(
        system=SYSTEM_PROMPT,
        user_message=user_message,
        max_tokens=max_tokens,
        temperature=temperature,
    ):
        yield delta
