"""Shared Claude client. Every backend Claude call goes through complete();
calls that need a typed answer use complete_structured(), which wraps it.

complete() calls client.messages.create() with the caller's kwargs unchanged
(tests patch Messages.create, see tests/fakes/claude.py), then logs usage.
"""
import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator, TypeVar

import anthropic
from anthropic.types import Message
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

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


class StructuredOutputError(RuntimeError):
    """A structured call did not return a valid answer. Callers decide what an
    explicit failure looks like for them; they must not substitute a made-up one."""


_Schema = TypeVar("_Schema", bound=BaseModel)


def complete_structured(
    *,
    schema: type[_Schema],
    tool_name: str,
    tool_description: str,
    model: str,
    messages: list[dict],
    max_tokens: int,
    user_id: str,
    event_type: str,
    system: Any = None,
    usage_metadata: dict[str, Any] | None = None,
) -> _Schema:
    """Call Claude and return its answer as a validated `schema` instance.

    The answer is requested as a forced tool call whose input must match the
    schema's JSON schema, so there is no free-text JSON to parse. A reply with
    no such tool call (for example cut off by max_tokens) or one that fails
    validation is retried once with the same request; both attempts are logged.
    If the second also fails, raises StructuredOutputError naming both
    failures. API errors propagate, as in complete() (the SDK retries those).
    """
    failures: list[str] = []
    for attempt in (1, 2):
        message = complete(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            user_id=user_id,
            event_type=event_type,
            system=system,
            usage_metadata=usage_metadata,
            tools=[{
                "name": tool_name,
                "description": tool_description,
                "input_schema": schema.model_json_schema(),
            }],
            tool_choice={"type": "tool", "name": tool_name},
        )
        tool_input = next(
            (block.input for block in message.content
             if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == tool_name),
            None,
        )
        if tool_input is None:
            failure = f"no {tool_name} tool call in the reply (stop_reason={message.stop_reason})"
        else:
            try:
                return schema.model_validate(tool_input)
            except ValidationError as exc:
                failure = f"reply does not match the schema: {exc}"
        failures.append(failure)
        logger.warning("llm.complete_structured: %s attempt %d of 2 failed: %s", event_type, attempt, failure)
    raise StructuredOutputError(
        f"{event_type}: no valid structured answer after 2 attempts. "
        f"First: {failures[0]} Second: {failures[1]}"
    )
