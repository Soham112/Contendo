"""POST /refine-selection: the prompt forbids invented facts, the rewrite is
checked by the specifics guard against the post's own sources, and bad input
gets a clear 4xx."""

import uuid

import pytest

A, B = "user-a", "user-b"
POST = "We rebuilt the ranking model last spring. It was slow at first. Then it got faster."
SELECTION = "It was slow at first."
TRACE_CHUNK = "Notes from the rebuild: p95 latency fell from 900 ms to 240 ms after the cache change."


def _body(**overrides):
    return {"selected_text": SELECTION, "instruction": "make it punchier", "full_post": POST, **overrides}


def _seed_trace(fake_db, user_id=A, *, post_id=None, no_specifics=False, created_at="2026-10-01T00:00:00Z"):
    trace_id = str(uuid.uuid4())
    fake_db.tables.setdefault("generation_traces", []).append({
        "id": trace_id,
        "user_id": user_id,
        "post_id": post_id,
        "created_at": created_at,
        "topic": "rebuilding a ranking model",
        "context": "it took 6 weeks",
        "retrieved": [{"chunk_id": "c1", "source_title": "Rebuild notes", "text": TRACE_CHUNK}],
        "retrieved_context": f"[Your own work] Rebuild notes:\n{TRACE_CHUNK}",
        "profile_snapshot": {"name": "Alice", "bio": "12 years in search"},
        "node_outputs": {"no_specifics": no_specifics},
    })
    return trace_id


def _trace_row(fake_db, trace_id):
    return next(t for t in fake_db.tables["generation_traces"] if t["id"] == trace_id)


def _prompt(claude, call=0) -> str:
    return claude.calls[call]["messages"][0]["content"]


@pytest.fixture
def post_refine(client, auth_headers):
    def _post(user_id=A, **overrides):
        return client.post("/refine-selection", headers=auth_headers(user_id), json=_body(**overrides))
    return _post


# --- The prompt ----------------------------------------------------------------

def test_prompt_never_asks_for_invented_events():
    import agents.humanizer_agent as humanizer_agent
    from agents.refine_agent import REFINE_SELECTION_PROMPT

    prompt = REFINE_SELECTION_PROMPT.lower()
    assert "sounds like it actually happened" not in prompt
    assert "never invent" in prompt
    assert "<note>" in prompt
    # The whole-post refine path and its prompt are gone.
    assert not hasattr(humanizer_agent, "REFINE_PROMPT")
    assert not hasattr(humanizer_agent, "refine_draft")


def test_refine_route_is_removed(client, auth_headers):
    resp = client.post("/refine", headers=auth_headers(A),
                       json={"current_draft": "d", "refinement_instruction": "i"})
    assert resp.status_code == 404


def test_instruction_reaches_the_model_unchanged(post_refine, claude):
    instruction = "Cut the hedging. Keep the second clause. No lists."
    claude.queue("It crawled at first.")

    assert post_refine(instruction=instruction).status_code == 200
    prompt = _prompt(claude)
    assert instruction in prompt
    assert "ACTION NEEDED" not in prompt


# --- Sources: the post's trace ---------------------------------------------------

def test_trace_id_puts_that_traces_sources_in_the_prompt(post_refine, claude, fake_db):
    trace_id = _seed_trace(fake_db)
    claude.queue("It crawled at first.")

    resp = post_refine(trace_id=trace_id)

    assert resp.status_code == 200
    assert resp.json() == {
        "rewritten_text": "It crawled at first.", "status": "ok", "message": "", "note": "",
        "sources_used": "trace", "sources_message": "",
    }
    assert TRACE_CHUNK in _prompt(claude)
    assert len(claude.calls) == 1


@pytest.mark.parametrize("rewritten", [
    "It was slow at first: p95 sat at 900 ms.",      # from a retrieved chunk
    "It was slow for the first 6 weeks.",            # from the trace's context
    "After 12 years in search, slow still stung.",   # from the trace's profile snapshot
])
def test_specifics_from_the_trace_are_allowed(post_refine, claude, fake_db, rewritten):
    trace_id = _seed_trace(fake_db)
    claude.queue(rewritten)

    resp = post_refine(trace_id=trace_id)

    assert resp.json()["status"] == "ok"
    assert resp.json()["rewritten_text"] == rewritten
    assert len(claude.calls) == 1


def test_specifics_from_the_instruction_are_allowed(post_refine, claude):
    claude.queue("It took 45 seconds per query at first.")

    resp = post_refine(instruction="say it took 45 seconds per query")

    assert resp.json()["status"] == "ok"
    assert resp.json()["rewritten_text"] == "It took 45 seconds per query at first."
    assert len(claude.calls) == 1


def test_post_id_finds_the_newest_linked_trace(post_refine, claude, fake_db):
    _seed_trace(fake_db, post_id=7, created_at="2026-09-01T00:00:00Z")
    fake_db.tables["generation_traces"][-1]["retrieved_context"] = "OLDER TRACE CONTEXT"
    _seed_trace(fake_db, post_id=7, created_at="2026-10-01T00:00:00Z")
    claude.queue("It crawled at first.")

    resp = post_refine(post_id=7)

    assert resp.json()["sources_used"] == "trace"
    assert TRACE_CHUNK in _prompt(claude)
    assert "OLDER TRACE CONTEXT" not in _prompt(claude)


def test_unknown_trace_id_falls_back_to_the_post_id(post_refine, claude, fake_db):
    _seed_trace(fake_db, post_id=7)
    claude.queue("It crawled at first.")

    resp = post_refine(trace_id=str(uuid.uuid4()), post_id=7)

    assert resp.json()["sources_used"] == "trace"


@pytest.mark.parametrize("by", ["trace_id", "post_id"])
def test_another_users_trace_is_never_used(post_refine, claude, fake_db, by):
    trace_id = _seed_trace(fake_db, user_id=B, post_id=7)
    claude.queue("It was slow at first: p95 sat at 900 ms.", "It crawled at first.")

    resp = post_refine(A, **({"trace_id": trace_id} if by == "trace_id" else {"post_id": 7}))

    body = resp.json()
    assert body["sources_used"] == "post_and_profile"
    assert TRACE_CHUNK not in _prompt(claude)
    # B's chunk does not make "900 ms" acceptable for A: the guard retried.
    assert len(claude.calls) == 2
    assert body["rewritten_text"] == "It crawled at first."


def test_no_specifics_trace_keeps_its_chunks_out(post_refine, claude, fake_db):
    trace_id = _seed_trace(fake_db, no_specifics=True)
    claude.queue("It was slow at first: p95 sat at 900 ms.", "It crawled at first.")

    resp = post_refine(trace_id=trace_id)

    assert TRACE_CHUNK not in _prompt(claude)
    assert len(claude.calls) == 2
    assert resp.json()["rewritten_text"] == "It crawled at first."


# --- The guard: retry once, then keep the original -----------------------------------

def test_invented_number_triggers_a_retry_then_the_fallback(post_refine, claude, fake_db):
    trace_id = _seed_trace(fake_db)
    claude.queue("It took 47 seconds per query at first.", "It ran 38% slower at first.")

    resp = post_refine(trace_id=trace_id)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "reverted"
    assert body["rewritten_text"] == SELECTION
    assert body["message"] == ("Couldn't refine without adding details that aren't in your sources. "
                               "Try adding them to your instruction.")
    assert len(claude.calls) == 2
    retry_prompt = _prompt(claude, 1)
    assert "47 seconds" in retry_prompt and "Your previous attempt" in retry_prompt
    assert "47 seconds" not in _prompt(claude, 0)


def test_clean_retry_is_accepted(post_refine, claude, fake_db):
    trace_id = _seed_trace(fake_db)
    claude.queue("It took 47 seconds per query at first.", "It crawled at first.")

    body = post_refine(trace_id=trace_id).json()

    assert body["status"] == "ok"
    assert body["rewritten_text"] == "It crawled at first."


def test_retry_is_logged_as_its_own_usage_event(post_refine, claude, monkeypatch):
    import llm.client as llm_client

    events = []
    monkeypatch.setattr(llm_client, "schedule_usage_event", lambda **kw: events.append(kw["event_type"]))
    claude.queue("It took 47 seconds per query at first.", "It crawled at first.")

    post_refine()

    assert events == ["refine_selection", "refine_selection_retry"]


# --- The guard result is recorded on the trace ---------------------------------------

def _guard_entries(fake_db, trace_id):
    return _trace_row(fake_db, trace_id)["node_outputs"].get("specifics_guard", [])


def test_revert_is_recorded_in_the_traces_specifics_guard(post_refine, claude, fake_db):
    trace_id = _seed_trace(fake_db)
    earlier = {"node": "humanizer", "iteration": 1, "outcome": "accepted_after_retry"}
    fake_db.tables["generation_traces"][-1]["node_outputs"]["specifics_guard"] = [earlier]
    claude.queue("It took 47 seconds per query at first.", "It ran 38% slower at first.")

    post_refine(trace_id=trace_id)

    entries = _guard_entries(fake_db, trace_id)
    assert entries[0] == earlier  # the pipeline's own entries are kept
    [entry] = entries[1:]
    assert entry["node"] == "refine_selection"
    assert entry["outcome"] == "reverted"
    assert [v["text"] for v in entry["first_attempt"]] == ["47 seconds"]
    assert [v["text"] for v in entry["retry"]] == ["38%"]
    # The rest of node_outputs is untouched.
    assert _trace_row(fake_db, trace_id)["node_outputs"]["no_specifics"] is False


def test_accepted_retry_is_recorded_too(post_refine, claude, fake_db):
    _seed_trace(fake_db, post_id=7)
    trace_id = fake_db.tables["generation_traces"][-1]["id"]
    claude.queue("It took 47 seconds per query at first.", "It crawled at first.")

    post_refine(post_id=7)  # trace found through the post

    [entry] = _guard_entries(fake_db, trace_id)
    assert entry["node"] == "refine_selection"
    assert entry["outcome"] == "accepted_after_retry"
    assert entry["retry"] == []


def test_clean_rewrite_writes_nothing_to_the_trace(post_refine, claude, fake_db):
    trace_id = _seed_trace(fake_db)
    claude.queue("It crawled at first.")

    post_refine(trace_id=trace_id)

    assert _guard_entries(fake_db, trace_id) == []
    assert ("generation_traces", "update") not in fake_db.log


def test_guard_result_is_never_written_to_another_users_trace(post_refine, claude, fake_db):
    trace_id = _seed_trace(fake_db, user_id=B, post_id=7)
    claude.queue("It took 47 seconds per query at first.", "It ran 38% slower at first.")

    post_refine(A, trace_id=trace_id, post_id=7)

    assert _guard_entries(fake_db, trace_id) == []
    assert ("generation_traces", "update") not in fake_db.log


def test_failing_to_record_the_guard_result_does_not_fail_the_request(post_refine, claude, fake_db, monkeypatch):
    import agents.refine_agent as refine_agent

    def boom(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(refine_agent, "append_trace_guard_entry", boom)
    trace_id = _seed_trace(fake_db)
    claude.queue("It took 47 seconds per query at first.", "It crawled at first.")

    resp = post_refine(trace_id=trace_id)

    assert resp.status_code == 200
    assert resp.json()["rewritten_text"] == "It crawled at first."


# --- No trace: post and profile only ---------------------------------------------------

def test_without_a_trace_it_uses_the_post_and_profile_and_says_so(post_refine, claude):
    from memory.profile_store import save_profile

    save_profile({"name": "Alice", "bio": "I have shipped 14 ranking models"}, user_id=A)
    claude.queue("Model 14 of 14 was slow at first.")

    resp = post_refine()

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sources_used"] == "post_and_profile"
    assert "post text and your profile only" in body["sources_message"]
    assert "No saved sources for this post" in _prompt(claude)


def test_without_a_trace_an_invented_number_still_reverts(post_refine, claude):
    claude.queue("It took 47 seconds per query at first.", "It ran 38% slower at first.")

    body = post_refine().json()

    assert body["status"] == "reverted"
    assert body["rewritten_text"] == SELECTION
    assert body["sources_used"] == "post_and_profile"


# --- The model's note --------------------------------------------------------------

def test_note_is_returned_separately_from_the_text(post_refine, claude):
    claude.queue("It crawled at first.\n<note>No source has a real example. Add one to your instruction.</note>")

    body = post_refine(instruction="add a real example").json()

    assert body["rewritten_text"] == "It crawled at first."
    assert body["note"] == "No source has a real example. Add one to your instruction."
    assert "<note>" not in body["rewritten_text"]


@pytest.mark.parametrize("reply", [
    "<note>No source has a real example.</note>",
    "<note>No source has a real example.",           # closing tag missing
])
def test_note_only_reply_leaves_the_selection_unchanged(post_refine, claude, reply):
    claude.queue(reply)

    body = post_refine(instruction="add a real example").json()

    assert body["status"] == "ok"
    assert body["rewritten_text"] == SELECTION
    assert body["note"] == "No source has a real example."


# --- Input validation and errors ---------------------------------------------------------

@pytest.mark.parametrize("overrides,status", [
    ({"selected_text": ""}, 400),
    ({"selected_text": "   \n"}, 400),
    ({"instruction": ""}, 400),
    ({"instruction": "  "}, 400),
    ({"full_post": ""}, 400),
    ({"selected_text": POST + " and more than the post"}, 400),
    ({"instruction": "x" * 2001}, 400),
    ({"full_post": "x" * 30001}, 400),
    ({"trace_id": "not-a-uuid"}, 422),
    ({"post_id": "seven"}, 422),
    ({"selected_text": None}, 422),
])
def test_invalid_input_is_a_4xx_before_any_claude_call(post_refine, claude, overrides, status):
    resp = post_refine(**overrides)

    assert resp.status_code == status
    assert claude.calls == []


def test_missing_fields_are_a_422(client, auth_headers, claude):
    resp = client.post("/refine-selection", headers=auth_headers(A), json={"instruction": "shorter"})
    assert resp.status_code == 422
    assert claude.calls == []


def test_unexpected_failure_is_a_generic_500(client, auth_headers, monkeypatch):
    import routers.generate as generate

    def boom(**kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(generate, "refine_selection", boom)
    resp = client.post("/refine-selection", headers=auth_headers(A), json=_body())

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Something went wrong. Please try again."}
    assert "secret internal detail" not in resp.text
