"""Chat API.

POST /api/chat returns a Server-Sent Events stream:

  event: token   data: <text delta>
  event: token   data: <text delta>
  ...
  event: done    data: {"citations": [...]}

The frontend appends token events to the message bubble and renders the
done payload as the citation panel.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db_session
from app.core.errors import GenerationError
from app.core.logging import get_logger
from app.schemas.chat import ChatRequest, Citation
from app.services import retrieval
from app.services.generation import (
    build_rag_prompt,
    extract_cited_ids,
)
from app.services.retrieval import RetrievedChunk

router = APIRouter()
logger = get_logger(__name__)

# TODO: replace with authenticated user_id once auth is wired up.
_DEFAULT_OWNER_ID = "local-user"

# Snippets shown in the citation panel are truncated to this length.
_SNIPPET_CHARS = 240


def _to_citations(
    cited_ids: list[str], chunks: list[RetrievedChunk]
) -> list[Citation]:
    """Map short_id citations the model emitted back to source chunks.

    Order = first appearance in the answer text.
    Unknown short_ids are silently dropped.
    """
    by_short = {f"c_{i}": ch for i, ch in enumerate(chunks)}
    out: list[Citation] = []
    for sid in cited_ids:
        ch = by_short.get(sid)
        if ch is None:
            continue
        snippet = (
            ch.text if len(ch.text) <= _SNIPPET_CHARS else ch.text[:_SNIPPET_CHARS] + "..."
        )
        out.append(
            Citation(
                short_id=sid,
                chunk_id=ch.id,
                document_id=ch.document_id,
                document_filename=ch.document_filename,
                page=ch.page,
                snippet=snippet,
                score=ch.score,
            )
        )
    return out


@router.post("")
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Stream a grounded answer with inline [c_<id>] citations."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="empty message")

    chunks = await retrieval.hybrid_search(
        db,
        req.message,
        owner_id=_DEFAULT_OWNER_ID,
        top_k=req.top_k,
    )

    user_message, _ = build_rag_prompt(req.message, chunks)

    async def event_stream() -> AsyncIterator[dict]:
        # Late import keeps the chat route from triggering Bedrock connection
        # until we actually need it.
        from app.adapters.bedrock import stream_chat
        from app.prompts.system import SYSTEM_PROMPT

        accumulated = ""
        try:
            async for delta in stream_chat(
                system=SYSTEM_PROMPT,
                user_message=user_message,
            ):
                accumulated += delta
                yield {"event": "token", "data": delta}
        except GenerationError as e:
            logger.warning("chat_generation_failed", error=str(e))
            yield {"event": "error", "data": json.dumps({"message": str(e)})}
            return

        cited_ids = extract_cited_ids(accumulated)
        citations = _to_citations(cited_ids, chunks)
        yield {
            "event": "done",
            "data": json.dumps(
                {"citations": [c.model_dump(mode="json") for c in citations]}
            ),
        }

    return EventSourceResponse(event_stream())
