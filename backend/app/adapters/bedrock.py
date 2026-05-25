"""Bedrock chat adapter.

Async streaming wrapper around invoke_model_with_response_stream for
Anthropic Claude models on Bedrock. Yields text deltas as they arrive
so the API can forward them over Server-Sent Events.

Uses the Anthropic messages format directly so swapping to Anthropic's
API would only require changing the HTTP transport, not the payload.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import boto3

from app.config import settings
from app.core.errors import GenerationError
from app.core.logging import get_logger

logger = get_logger(__name__)


_DEFAULT_MAX_TOKENS = 1024


def _client() -> Any:
    """boto3 bedrock-runtime client. Created on demand; clients are cheap."""
    return boto3.client("bedrock-runtime", region_name=settings.aws_region)


async def stream_chat(
    *,
    system: str,
    user_message: str,
    model_id: str | None = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = 0.1,
) -> AsyncIterator[str]:
    """Yield text deltas from Claude as they stream in.

    The boto3 streaming response is synchronous; we hand the chunked
    iteration off to a background thread and pipe deltas through an
    asyncio queue so the FastAPI event loop never blocks.
    """
    model_id = model_id or settings.bedrock_text_model_id

    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user_message}],
        }
    )

    queue: asyncio.Queue[str | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _consume() -> None:
        try:
            resp = _client().invoke_model_with_response_stream(
                modelId=model_id, body=body
            )
            for event in resp["body"]:
                payload = json.loads(event["chunk"]["bytes"])
                etype = payload.get("type")
                if etype == "content_block_delta":
                    delta = payload.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            asyncio.run_coroutine_threadsafe(queue.put(text), loop)
                # Other event types (message_start, content_block_start,
                # message_stop, etc.) we don't need to surface.
        except Exception as e:  # noqa: BLE001 - boto3 surface is broad
            logger.exception("bedrock_stream_error")
            asyncio.run_coroutine_threadsafe(
                queue.put(f"__ERROR__:{type(e).__name__}: {e}"), loop
            )
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)  # sentinel

    asyncio.create_task(asyncio.to_thread(_consume))

    while True:
        item = await queue.get()
        if item is None:
            return
        if item.startswith("__ERROR__:"):
            raise GenerationError(item[len("__ERROR__:") :])
        yield item
