"""llm/client.py: the shared Claude client and complete()."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest


@pytest.fixture
def usage_calls(monkeypatch):
    """Records every schedule_usage_event() call made by complete()."""
    import llm.client as llm_client

    calls: list[dict] = []
    monkeypatch.setattr(llm_client, "schedule_usage_event", lambda **kw: calls.append(kw))
    return calls


def _complete(**overrides):
    from llm.client import SONNET, complete

    kwargs = dict(
        model=SONNET,
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
        user_id="user-a",
        event_type="test_event",
    )
    kwargs.update(overrides)
    return complete(**kwargs)


# --- kwargs pass-through ------------------------------------------------------

def test_kwargs_reach_messages_create_unchanged(claude, usage_calls):
    from llm.client import SONNET

    claude.queue("ok")
    messages = [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]
    msg = _complete(
        model=SONNET,
        messages=messages,
        max_tokens=321,
        system="be brief",
        stop_sequences=["END"],
        metadata={"user_id": "anthropic-side-id"},
    )

    assert msg.content[0].text == "ok"
    assert claude.calls == [{
        "model": SONNET,
        "max_tokens": 321,
        "messages": messages,
        "system": "be brief",
        "stop_sequences": ["END"],
        "metadata": {"user_id": "anthropic-side-id"},
    }]


def test_no_system_kwarg_when_system_is_none(claude, usage_calls):
    claude.queue("ok")
    _complete()
    assert "system" not in claude.calls[0]
    # user_id / event_type / usage_metadata are ours, never sent to Anthropic.
    assert set(claude.calls[0]) == {"model", "max_tokens", "messages"}


def test_unknown_model_is_rejected_before_any_claude_call(claude, usage_calls):
    with pytest.raises(ValueError):
        _complete(model="claude-some-other-model")
    assert claude.calls == []
    assert usage_calls == []


def test_api_errors_propagate_and_log_no_usage(claude, usage_calls):
    # Nothing queued: the fake raises, as a real API error would.
    with pytest.raises(AssertionError):
        _complete()
    assert usage_calls == []


# --- usage logging ------------------------------------------------------------

@pytest.mark.parametrize("model_name,label", [("SONNET", "sonnet"), ("HAIKU", "haiku")])
def test_usage_logged_with_event_type_label_and_token_counts(claude, usage_calls, model_name, label):
    import llm.client as llm_client

    claude.queue("ok")
    _complete(model=getattr(llm_client, model_name), event_type="critic", user_id="user-b")

    assert usage_calls == [{
        "user_id": "user-b",
        "event_type": "critic",
        "input_tokens": 10,   # the fake reports 10/10
        "output_tokens": 10,
        "metadata": None,
        "model": label,
    }]


def test_usage_metadata_goes_to_usage_log_not_to_claude(claude, usage_calls):
    claude.queue("ok")
    _complete(usage_metadata={"topic": "t"})
    assert usage_calls[0]["metadata"] == {"topic": "t"}
    assert "usage_metadata" not in claude.calls[0]
    assert "metadata" not in claude.calls[0]


def test_failing_usage_logger_does_not_break_complete(claude, monkeypatch):
    import llm.client as llm_client

    def broken(**kwargs):
        raise RuntimeError("usage store down")

    monkeypatch.setattr(llm_client, "schedule_usage_event", broken)
    claude.queue("still fine")
    assert _complete().content[0].text == "still fine"


def test_usage_reaches_usage_store_end_to_end(client, claude, monkeypatch):
    """Through the real schedule_usage_event and the app's event loop."""
    import time
    import memory.usage_store as usage_store
    from starlette.concurrency import run_in_threadpool

    rows: list[dict] = []

    async def fake_insert(payload):
        rows.append(payload)

    monkeypatch.setattr(usage_store, "_insert_event", fake_insert)
    claude.queue("ok")
    client.portal.call(run_in_threadpool, lambda: _complete(event_type="critic"))

    deadline = time.monotonic() + 5
    while not rows and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "critic"
    assert rows[0]["user_id"] == "user-a"
    assert rows[0]["metadata"] == {}


# --- trace hook ---------------------------------------------------------------

def test_trace_collects_calls_when_set(claude, usage_calls):
    from llm.client import HAIKU, SONNET, trace_calls

    claude.queue("a", "b")
    with trace_calls() as calls:
        _complete(model=SONNET, event_type="first")
        _complete(model=HAIKU, event_type="second")

    assert [(c["event_type"], c["model"]) for c in calls] == [("first", SONNET), ("second", HAIKU)]
    for c in calls:
        assert c["input_tokens"] == 10 and c["output_tokens"] == 10
        assert c["latency_ms"] >= 0
    assert set(calls[0]) == {"event_type", "model", "input_tokens", "output_tokens", "latency_ms"}


def test_trace_does_nothing_when_unset(claude, usage_calls):
    import llm.client as llm_client

    claude.queue("a", "b")
    with llm_client.trace_calls() as calls:
        _complete()
    _complete()  # after the block: not traced, and doesn't fail

    assert len(calls) == 1
    assert llm_client._trace.get() is None


def test_trace_follows_run_in_threadpool_but_not_executor_submit(claude, usage_calls):
    """Documents the ContextVar caveat in llm/client.py."""
    from starlette.concurrency import run_in_threadpool

    from llm.client import trace_calls

    claude.queue("a", "b")

    async def run():
        with trace_calls() as calls:
            await run_in_threadpool(_complete, event_type="threadpool")
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(_complete, event_type="executor").result()
        return calls

    calls = asyncio.run(run())
    assert [c["event_type"] for c in calls] == ["threadpool"]
    assert len(claude.calls) == 2  # both calls happened; only one was traced


# --- pilot: critic_agent ------------------------------------------------------

def test_critic_node_goes_through_complete(claude, usage_calls):
    from agents.critic_agent import critic_node
    from llm.client import HAIKU, trace_calls

    claude.queue("not json, parse falls back")
    state = {"user_id": "user-c", "quality": "standard", "current_draft": "draft", "archetype": "contrarian_take"}

    with trace_calls() as calls:
        critic_node(state)

    assert claude.calls[0]["model"] == HAIKU
    assert claude.calls[0]["max_tokens"] == 600
    assert set(claude.calls[0]) == {"model", "max_tokens", "messages"}
    assert usage_calls[0]["event_type"] == "critic"
    assert usage_calls[0]["model"] == "haiku"
    assert usage_calls[0]["user_id"] == "user-c"
    assert [c["event_type"] for c in calls] == ["critic"]
