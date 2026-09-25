"""Fake for the Anthropic Messages API.

Every Claude call in the backend goes through anthropic's Messages.create.
Tests patch it so no real request is ever made. A call with no queued response
fails the test loudly, so a new, unexpected Claude call can't slip through.

    def test_x(claude):
        claude.queue('{"score": 80}')           # next call returns this text
        claude.respond_with(lambda kw: "...")   # or compute from the request
        ...
        assert claude.calls[0]["model"] == "claude-sonnet-4-6"
"""

from __future__ import annotations

from typing import Callable

from anthropic.types import Message, TextBlock, Usage


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
        return Message(
            id=f"msg_fake_{len(self.calls)}",
            type="message",
            role="assistant",
            model=kwargs.get("model", "fake"),
            content=[TextBlock(type="text", text=text)],
            stop_reason="end_turn",
            stop_sequence=None,
            usage=Usage(input_tokens=10, output_tokens=10),
        )
