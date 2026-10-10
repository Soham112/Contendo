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

from llm import models
from memory.usage_store import schedule_usage_event

load_dotenv()

logger = logging.getLogger(__name__)

# Pipeline A's models, and every call outside the single-writer pipeline. The
# id strings, and the per-role models of variants B and C, are in llm/models.py.
SONNET = models.SONNET_4_6
HAIKU = models.HAIKU_4_5

# The most output a call here should ask for. Every call is non-streaming, and
# Anthropic's guidance for non-streaming requests is to stay near 16,000 output
# tokens so a response fits the SDK's HTTP timeout. The models' own caps are far
# higher (128,000 for Sonnet 4.6). A budget above this needs streaming first.
MAX_NON_STREAMING_OUTPUT_TOKENS = 16_000

# Room added to a call's max_tokens on a model that thinks by default: thinking
# counts against max_tokens, so a budget sized for the answer alone can be used
# up before any text is written. STOPGAP (provisional value): no thinking measurement exists yet
# for these prompts. 8,000 keeps the largest draft budget (long-form, about
# 5,600 tokens on the newer tokenizer) under the non-streaming ceiling; replace
# it with the thinking_tokens the step 7 runs record (evals ablation.md,
# "Draft budget").
THINKING_ALLOWANCE_TOKENS = 8_000

REFUSAL = "refusal"   # stop_reason of a reply a safety classifier declined


def output_budget(model: str, answer_tokens: int) -> int:
    """max_tokens for a call whose answer needs answer_tokens: unchanged for a
    model that does not think, plus THINKING_ALLOWANCE_TOKENS for one that
    does, never above the non-streaming ceiling."""
    if not models.spec(model).thinks:
        return answer_tokens
    return min(MAX_NON_STREAMING_OUTPUT_TOKENS, answer_tokens + THINKING_ALLOWANCE_TOKENS)


def message_text(message: Message) -> str:
    """The reply's text: its text blocks, joined. A model that thinks puts
    thinking blocks first, so content[0] is not the answer; a refused or
    cut-off reply may hold no text block at all, which gives ""."""
    return "".join(block.text for block in message.content if getattr(block, "type", "") == "text")


def _thinking_tokens(usage: Any) -> int:
    """usage.output_tokens_details.thinking_tokens, 0 when the reply has none.
    The field is newer than the pinned SDK's Usage type, which then keeps it as
    a plain dict."""
    details = getattr(usage, "output_tokens_details", None)
    if details is None:
        return 0
    value = details.get("thinking_tokens") if isinstance(details, dict) else getattr(details, "thinking_tokens", None)
    return int(value or 0)

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
    """Collect every complete() call made in this context: `with trace_calls() as calls:`.

    Traces nest: a step that measures its own calls does not hide them from the
    trace around it. When the inner block ends, its calls are added to the outer
    list, in order."""
    outer = _trace.get()
    calls: list[dict] = []
    token = _trace.set(calls)
    try:
        yield calls
    finally:
        _trace.reset(token)
        if outer is not None:
            outer.extend(calls)


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
    models.spec(model)   # raises for a model llm.models does not list

    create_kwargs: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system is not None:
        create_kwargs["system"] = system
    create_kwargs.update(kwargs)

    start = time.perf_counter()
    try:
        message = client.messages.create(**create_kwargs)
    except ValidationError as exc:
        # SDK validation can also fail before a caller validates its tool input.
        raise StructuredOutputError(_validation_summary(exc, Message)) from None
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
            model=model,
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
            "thinking_tokens": _thinking_tokens(message.usage),
            "stop_reason": message.stop_reason,
            "latency_ms": latency_ms,
        })

    return message


class StructuredOutputError(RuntimeError):
    """A structured call did not return a valid answer. Callers decide what an
    explicit failure looks like for them; they must not substitute a made-up one."""


class TruncatedStructuredOutputError(StructuredOutputError):
    """Both structured attempts exhausted their output budget."""


class RefusedStructuredOutputError(StructuredOutputError):
    """The model declined the request (stop_reason "refusal"). Not retried: the
    same request would be declined again."""


# Bounds each diagnostic (and the combined final error), keeping logs/traces
# useful without allowing a malformed response to flood them with field errors.
MAX_STRUCTURED_ERROR_CHARS = 512


def _validation_summary(exc: ValidationError, schema: type[BaseModel]) -> str:
    """Only schema-owned field paths and error types; never values/messages/ctx.

    Dynamic dictionary keys are user data, so paths not declared in the schema
    use a constant placeholder rather than echoing their contents.
    """
    fields: set[str] = set()
    def collect(value: Any) -> None:
        if isinstance(value, dict):
            fields.update(value.get("properties", {}))
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    collect(schema.model_json_schema())
    errors = exc.errors(include_input=False, include_context=False, include_url=False)
    pieces = []
    for error in errors:
        path = ".".join(
            str(part) if isinstance(part, int) or part in fields else "<key>"
            for part in error["loc"]
        ) or "<root>"
        pieces.append(f"{path}: {error['type']}")
        if len("; ".join(pieces)) >= MAX_STRUCTURED_ERROR_CHARS:
            break
    return ("validation_error: " + "; ".join(pieces))[:MAX_STRUCTURED_ERROR_CHARS]


_Schema = TypeVar("_Schema", bound=BaseModel)

TOOL_INSTRUCTION = "Answer by calling the {tool_name} tool, and write nothing outside that call."


def _with_tool_instruction(messages: list[dict], tool_name: str) -> list[dict]:
    """messages with TOOL_INSTRUCTION added to the end of the last one (a
    string prompt, as every structured caller sends). The caller's list is not changed."""
    last = messages[-1]
    if not isinstance(last["content"], str):
        raise TypeError("complete_structured: the last message's content must be a string")
    return [*messages[:-1], {**last, "content": f"{last['content']}\n\n{TOOL_INSTRUCTION.format(tool_name=tool_name)}"}]


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

    The answer is requested as a tool call whose input must match the schema's
    JSON schema, so there is no free-text JSON to parse. Where the model accepts
    it the tool is forced. Claude Opus 5.5 and Sonnet 5.5 reject a forced tool
    choice with a 400 (llm.models.ModelSpec.forced_tool_choice): for them the
    request sends tool_choice "auto" and ends the prompt with an instruction to
    call the tool. Nothing guarantees the call then, so its absence is one of
    the failures below. On a model that thinks, max_tokens gets room for the
    thinking (output_budget).

    A reply with stop_reason=max_tokens (even with valid tool input), no tool
    call, or one that fails validation is retried once with the same request;
    both attempts are logged. If the second also fails, raises
    StructuredOutputError naming both failures. A refusal raises
    RefusedStructuredOutputError at once. API errors propagate, as in
    complete() (the SDK retries those).
    """
    failures: list[str] = []
    truncations = 0
    if models.spec(model).forced_tool_choice:
        tool_choice = {"type": "tool", "name": tool_name}
    else:
        tool_choice = {"type": "auto"}
        messages = _with_tool_instruction(messages, tool_name)
    for attempt in (1, 2):
        message = complete(
            model=model,
            messages=messages,
            max_tokens=output_budget(model, max_tokens),
            user_id=user_id,
            event_type=event_type,
            system=system,
            usage_metadata=usage_metadata,
            tools=[{
                "name": tool_name,
                "description": tool_description,
                "input_schema": schema.model_json_schema(),
            }],
            tool_choice=tool_choice,
        )
        if message.stop_reason == REFUSAL:
            raise RefusedStructuredOutputError(f"{event_type}: the model declined the request (stop_reason=refusal)")
        tool_input = next(
            (block.input for block in message.content
             if getattr(block, "type", "") == "tool_use" and getattr(block, "name", "") == tool_name),
            None,
        )
        if message.stop_reason == "max_tokens":
            truncations += 1
            failure = "truncated (stop_reason=max_tokens)"
        elif tool_input is None:
            failure = f"no {tool_name} tool call in the reply (stop_reason={message.stop_reason})"
        else:
            try:
                return schema.model_validate(tool_input)
            except ValidationError as exc:
                failure = f"reply does not match the schema: {_validation_summary(exc, schema)}"[:MAX_STRUCTURED_ERROR_CHARS]
        failures.append(failure)
        logger.warning("llm.complete_structured: %s attempt %d of 2 failed: %s", event_type, attempt, failure)
    error = TruncatedStructuredOutputError if truncations == 2 else StructuredOutputError
    raise error(
        f"{event_type}: no valid structured answer after 2 attempts. "
        f"First: {failures[0]} Second: {failures[1]}"[:MAX_STRUCTURED_ERROR_CHARS]
    )
