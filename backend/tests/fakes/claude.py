"""Fake for the Anthropic Messages API.

Every Claude call in the backend goes through anthropic's Messages.create.
Tests patch it so no real request is ever made. A call with no queued response
fails the test loudly, so a new, unexpected Claude call can't slip through.

    def test_x(claude):
        claude.queue('{"score": 80}')           # next call returns this text
        claude.respond_with(lambda kw: "...")   # or compute from the request
        ...
        assert claude.calls[0]["model"] == "claude-sonnet-4-6"

Structured calls (llm.client.complete_structured) force a tool call. For those,
a queued response that is a JSON object is returned as that tool's input; any
other text is returned as plain text, which is how a test makes a structured
call fail ("the model did not call the tool").
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Callable

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage


class UnexpectedClaudeCall(AssertionError):
    pass


class FakeClaude:
    def __init__(self):
        self.calls: list[dict] = []
        self._queue: list[str | Message] = []
        self._responder: Callable[[dict], str] | None = None

    def reset(self) -> None:
        self.calls.clear()
        self._queue.clear()
        self._responder = None

    def queue(self, *texts: str | Message) -> None:
        self._queue.extend(texts)

    def respond_with(self, fn: Callable[[dict], str]) -> None:
        self._responder = fn

    def _next_text(self, kwargs: dict) -> str | Message:
        if self._queue:
            return self._queue.pop(0)
        if self._responder is not None:
            return self._responder(kwargs)
        messages = kwargs.get("messages") or [{}]
        preview = str(messages[-1].get("content", ""))[:120]
        raise UnexpectedClaudeCall(
            f"Unmocked Claude call (model={kwargs.get('model')}). "
            f"Queue a response with claude.queue(...). Prompt starts: {preview!r}"
        )

    def stream(self, **kwargs) -> "FakeStream":
        """messages.stream(): the same answer as create(), as text deltas."""
        return FakeStream(self.create(**kwargs))

    def create(self, **kwargs) -> Message:
        self.calls.append(kwargs)
        text = self._next_text(kwargs)
        if isinstance(text, Message):
            return text
        block, stop_reason = TextBlock(type="text", text=text), "end_turn"
        forced_tool = (kwargs.get("tool_choice") or {}).get("name")
        if forced_tool:
            try:
                tool_input = json.loads(text)
            except ValueError:
                tool_input = None
            if isinstance(tool_input, dict):
                block = ToolUseBlock(type="tool_use", id=f"toolu_fake_{len(self.calls)}",
                                     name=forced_tool, input=tool_input)
                stop_reason = "tool_use"
        return Message(
            id=f"msg_fake_{len(self.calls)}",
            type="message",
            role="assistant",
            model=kwargs.get("model", "fake"),
            content=[block],
            stop_reason=stop_reason,
            stop_sequence=None,
            usage=Usage(input_tokens=10, output_tokens=10),
        )


class FakeStream:
    """A messages.stream() context: one text delta per text block, then the final message."""

    def __init__(self, message: Message):
        self._message = message

    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def __iter__(self):
        for block in self._message.content:
            if block.type == "text":
                yield SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text=block.text))

    def get_final_message(self) -> Message:
        return self._message


def sse_body(message: Message) -> str:
    """The server-sent events the Messages API streams for `message`: what the
    real SDK's messages.stream() reads back into the same Message."""
    def event(kind: str, data: dict) -> str:
        return f"event: {kind}\ndata: {json.dumps({'type': kind, **data})}\n\n"

    dumped = message.model_dump(mode="json")
    start = {**dumped, "content": [], "stop_reason": None, "stop_sequence": None, "stop_details": None}
    events = [event("message_start", {"message": start})]
    for index, block in enumerate(dumped["content"]):
        if block["type"] == "text":
            opening, deltas = {**block, "text": ""}, [{"type": "text_delta", "text": block["text"]}]
        elif block["type"] == "thinking":
            opening = {**block, "thinking": "", "signature": ""}
            deltas = [{"type": "thinking_delta", "thinking": block["thinking"]},
                      {"type": "signature_delta", "signature": block["signature"]}]
        else:
            opening, deltas = block, []
        events.append(event("content_block_start", {"index": index, "content_block": opening}))
        events += [event("content_block_delta", {"index": index, "delta": delta}) for delta in deltas]
        events.append(event("content_block_stop", {"index": index}))
    events.append(event("message_delta", {
        "delta": {"stop_reason": dumped["stop_reason"], "stop_sequence": dumped["stop_sequence"],
                  "stop_details": dumped.get("stop_details")},
        "usage": dumped["usage"]}))
    events.append(event("message_stop", {}))
    return "".join(events)
