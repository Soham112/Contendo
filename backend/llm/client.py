"""Shared Claude client. Every backend Claude call goes through complete().

complete() calls client.messages.create() with the caller's kwargs unchanged
(tests patch Messages.create, see tests/fakes/claude.py), then logs usage.
"""
import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

import anthropic
from anthropic.types import Message
from dotenv import load_dotenv

from memory.usage_store import schedule_usage_event

load_dotenv()

logger = logging.getLogger(__name__)

# The only place model strings live.
SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"

# Label passed to usage logging (usage_store prices by it).
_USAGE_LABELS = {SONNET: "sonnet", HAIKU: "haiku"}

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

# Trace hook: when set to a list, complete() appends one entry per call.
# run_in_threadpool copies the caller's context into the worker thread, so calls
# made there are traced. ThreadPoolExecutor.submit() does NOT propagate
# ContextVars, so calls made from executor threads (e.g. the parallel entity
# extraction in ingestion_agent._store_entities_for_chunks) are not traced.
_trace: ContextVar[list[dict] | None] = ContextVar("llm_trace", default=None)


@contextmanager
def trace_calls() -> Iterator[list[dict]]:
    """Collect every complete() call made in this context: `with trace_calls() as calls:`."""
    calls: list[dict] = []
    token = _trace.set(calls)
    try:
        yield calls
    finally:
        _trace.reset(token)


def complete(
    *,
    model: str,
    messages: list[dict],
    max_tokens: int,
    user_id: str,
    event_type: str,
    system: Any = None,
    usage_metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Message:
    """Call Claude and log usage. API errors propagate; logging never raises.

    `usage_metadata` goes to the usage_events row only. Any other kwargs are
    passed to messages.create() unchanged (so Anthropic's own `metadata` stays
    available).
    """
    if model not in _USAGE_LABELS:
        raise ValueError(f"Unknown model {model!r}: use llm.client.SONNET or llm.client.HAIKU")

    create_kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system is not None:
        create_kwargs["system"] = system
    create_kwargs.update(kwargs)

    start = time.perf_counter()
    message = client.messages.create(**create_kwargs)
    latency_ms = (time.perf_counter() - start) * 1000

    try:
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
    except Exception:
        logger.warning("llm.complete: response for %s has no usage; skipping usage log", event_type)
        return message

    try:
        schedule_usage_event(
            user_id=user_id,
            event_type=event_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata=usage_metadata,
            model=_USAGE_LABELS[model],
        )
    except Exception as exc:
        logger.warning("llm.complete: usage logging failed for %s: %s", event_type, exc)

    calls = _trace.get()
    if calls is not None:
        calls.append({
            "event_type": event_type,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
        })

    return message
