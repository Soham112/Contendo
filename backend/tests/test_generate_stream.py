"""Phase 2 streaming: the draft preview filter, complete(on_text=...), and
POST /generate/stream."""

import json
import random

import anthropic
import httpx
import pytest
from anthropic.types import TextBlock

from tests.generation_fixtures import one_call_reply
from tests.length_fixtures import KB_USER
from tests.test_generation_trace import seeded_kb  # noqa: F401
from tests.test_models import _reply, _thinking_block
from utils.draft_preview import DraftPreview, preview_text

POST = ("pgvector made our retrieval fast [[S1]].\n\n"
        "We kept the index small [[S1,S2]], and it held up [[V]].\n\n"
        "That is the whole trick [[R]].")
SHOWN = ("pgvector made our retrieval fast.\n\n"
         "We kept the index small, and it held up.\n\n"
         "That is the whole trick.")
RAW = one_call_reply(POST, structure="incident_report", event='S1 | "We moved to pgvector."')


def _streamed(raw: str, cuts: list[int]) -> list[str]:
    preview, pieces, last = DraftPreview(), [], 0
    for cut in [*cuts, len(raw)]:
        pieces.append(preview.feed(raw[last:cut]))
        last = cut
    return pieces


# --- the preview filter --------------------------------------------------------

def test_preview_shows_only_the_post_without_markers():
    assert preview_text(RAW) == SHOWN


@pytest.mark.parametrize("seed", range(20))
def test_preview_is_the_same_however_the_text_is_split(seed):
    rng = random.Random(seed)
    cuts = sorted(rng.sample(range(1, len(RAW)), rng.randint(1, 40)))
    assert "".join(_streamed(RAW, cuts)) == SHOWN


def test_one_character_at_a_time_never_shows_a_marker_or_a_tag():
    pieces = _streamed(RAW, list(range(1, len(RAW))))
    shown = ""
    for piece in pieces:
        shown += piece
        assert "[" not in shown and "<" not in shown and "S1 |" not in shown
        assert SHOWN.startswith(shown)
    assert shown == SHOWN


@pytest.mark.parametrize("raw, shown", [
    ("<structure>general</structure>\n<post>\nHalf a sente", "Half a sente"),
    ("<post>\nIt held [[S", "It held"),
    ("<post>\nIt held [", "It held"),
    ("<post>\nIt held </po", "It held"),
    ("<post>\nIt held   ", "It held"),
    ("<event>S1 | \"x\"</event>\n<po", ""),
    ("<post>\nBroken [[S1 marker\nnext line", "Broken [[S1 marker\nnext line"),   # not a marker: no ]] on its line
    ("<post>\nA [DIAGRAM: flow]", "A [DIAGRAM: flow]"),
    ("<post>\nDone [[V]].\n</post>\ntrailing junk", "Done."),
])
def test_partial_drafts(raw, shown):
    assert preview_text(raw) == shown


def test_preview_text_of_a_shorter_raw_is_always_a_prefix():
    for end in range(len(RAW) + 1):
        assert preview_text(RAW).startswith(preview_text(RAW[:end]))


# --- complete(on_text=...) -------------------------------------------------------

def _complete(**overrides):
    from llm.client import SONNET, complete

    return complete(model=SONNET, messages=[{"role": "user", "content": "hi"}], max_tokens=100,
                    user_id="user-a", event_type="test_event", **overrides)


def test_on_text_hears_text_deltas_and_not_thinking(claude, wire):
    claude.queue(_reply(_thinking_block(), TextBlock(type="text", text="The answer.")))
    heard = []
    message = _complete(on_text=heard.append)
    assert "".join(heard) == "The answer."
    assert wire[0]["body"].get("stream") is True
    assert message.content[-1].text == "The answer."


def test_a_failing_listener_never_fails_the_call(claude, caplog):
    claude.queue("The answer.")

    def broken(_):
        raise RuntimeError("listener bug")

    message = _complete(on_text=broken)
    assert message.content[0].text == "The answer."
    assert "text listener failed" in caplog.text


# --- POST /generate/stream ---------------------------------------------------------

REQUEST = {"topic": "pgvector retrieval", "tone": "casual"}


def _events(response) -> list[tuple[str, dict]]:
    events = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def _stream(client, auth_headers, body=REQUEST):
    return client.post("/generate/stream", headers=auth_headers(KB_USER), json=body)


def test_stream_sends_the_preview_then_the_same_final_as_generate(client, auth_headers, claude, fake_db, seeded_kb):
    claude.queue(one_call_reply(POST))
    response = _stream(client, auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response)
    kinds = [kind for kind, _ in events]
    assert kinds[-1] == "final" and set(kinds[:-1]) == {"delta"}
    assert "".join(data["text"] for _, data in events[:-1]) == SHOWN
    final = events[-1][1]

    claude.queue(one_call_reply(POST))
    plain = client.post("/generate", headers=auth_headers(KB_USER), json=REQUEST).json()
    assert final["status"] == plain["status"] == "ok"
    assert final["post"] == plain["post"]
    assert final.keys() == plain.keys()
    assert final["trace_id"] and len(claude.calls) == 2


def test_a_run_with_no_post_ends_with_its_status_and_gives_the_generation_back(
        client, auth_headers, claude, fake_db, seeded_kb, monkeypatch):
    import routers.generate as generate

    released = []
    monkeypatch.setattr(generate, "_release_generation", lambda user_id, period: released.append(user_id))
    claude.queue("<post></post>")
    events = _events(_stream(client, auth_headers))
    assert [kind for kind, _ in events] == ["final"]
    assert events[0][1]["status"] == "draft_empty" and events[0][1]["post"] == ""
    assert released == [KB_USER]


def test_an_api_error_mid_run_is_an_error_event(client, auth_headers, claude, fake_db, seeded_kb, monkeypatch):
    import routers.generate as generate

    released = []
    monkeypatch.setattr(generate, "_release_generation", lambda user_id, period: released.append(user_id))

    def overloaded(kwargs):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.InternalServerError("overloaded", response=httpx.Response(529, request=request), body=None)

    claude.respond_with(overloaded)
    events = _events(_stream(client, auth_headers))
    assert [kind for kind, _ in events] == ["error"]
    assert events[0][1]["status_code"] == 503 and "overloaded" in events[0][1]["detail"].lower()
    assert released == [KB_USER]


def test_an_internal_error_never_leaks_its_message(client, auth_headers, claude, fake_db, seeded_kb, monkeypatch):
    import routers.generate as generate

    def broken(**kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(generate, "run_pipeline", broken)
    response = _stream(client, auth_headers)
    assert _events(response) == [("error", {"status_code": 500, "detail": generate._GENERIC_500})]
    assert "secret internal detail" not in response.text


def test_stream_requires_a_token(client):
    assert client.post("/generate/stream", json=REQUEST).status_code == 401


def test_a_bad_request_is_rejected_before_the_stream_starts(client, auth_headers, claude):
    response = _stream(client, auth_headers, {**REQUEST, "topic": "  "})
    assert response.status_code == 400 and response.json()["detail"] == "topic is required"
    assert claude.calls == []


def test_quota_is_checked_before_the_stream_starts(client, auth_headers, claude, monkeypatch):
    import routers.generate as generate
    from billing.gates import quota_exceeded

    async def at_limit(user_id):
        raise quota_exceeded(generate.get_entitlements(user_id))

    monkeypatch.setattr("routers.generate_stream.reserve_generation", at_limit)
    response = _stream(client, auth_headers)
    assert response.status_code == 402 and claude.calls == []
