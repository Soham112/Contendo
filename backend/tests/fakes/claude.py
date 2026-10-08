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
from typing import Callable

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage


class UnexpectedClaudeCall(AssertionError):
    pass


class FakeClaude:
    def __init__(self):
        self.calls: list[dict] = []
        self._queue: list[str] = []
        self._responder: Callable[[dict], str] | None = None

    def reset(self) -> None:
        self.calls.clear()
        self._queue.clear()
        self._responder = None

    def queue(self, *texts: str) -> None:
        self._queue.extend(texts)

    def respond_with(self, fn: Callable[[dict], str]) -> None:
        self._responder = fn

    def _next_text(self, kwargs: dict) -> str:
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

    def create(self, **kwargs) -> Message:
        self.calls.append(kwargs)
        text = self._next_text(kwargs)
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
