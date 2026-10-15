"""Selection refine on a single-writer post (its trace stored a source index):
the post's own drafter, the stored sources block, a marker on every sentence,
the deterministic checks on the passage, one retry, then the selection is kept.
Posts without a source index keep the earlier writer (test_refine_selection.py)."""

import json

import pytest
from anthropic.types import Message, RefusalStopDetails, TextBlock, Usage

from llm.models import OPUS_5_5, SONNET_4_6
from tests.length_fixtures import KB_USER, _outputs, _run
from tests.review_fixtures import answer_pipeline
from tests.test_generation_trace import seeded_kb  # noqa: F401  (shared fixture)

DRAFT = "pgvector makes retrieval fast. [[S1]]\n\nThat is most of the argument. [[V]]"
POST = "pgvector makes retrieval fast.\n\nThat is most of the argument."
SELECTION = "pgvector makes retrieval fast."
GOOD = "Retrieval gets fast with pgvector. [[S1]]"
INVENTED = "pgvector made retrieval 40 percent faster. [[S1]]"
REVERTED = "Couldn't refine without adding details that aren't in your sources. Try adding them to your instruction."


@pytest.fixture
def post(claude, fake_db, seeded_kb):
    """A post written by the default pipeline, and its trace id."""
    answer_pipeline(claude, [DRAFT])
    result = _run(None)
    assert result["status"] == "ok" and result["post"] == POST
    claude.reset()
    return result["trace_id"]


@pytest.fixture
def refine(client, auth_headers, post):
    def _refine(**overrides):
        body = {"selected_text": SELECTION, "instruction": "make it punchier", "full_post": POST, "trace_id": post, **overrides}
        return client.post("/refine-selection", headers=auth_headers(KB_USER), json=body)
    return _refine


def _prompt(claude, call=0) -> str:
    return claude.calls[call]["messages"][0]["content"]


def _refines(fake_db) -> list[dict]:
    return _outputs(fake_db)["refine_selection"]


# --- The call ---------------------------------------------------------------------

def test_the_posts_own_drafter_rewrites_it_with_its_effort_and_room_to_think(refine, claude, fake_db):
    from llm.client import THINKING_ALLOWANCE_TOKENS
    from llm.models import OPUS_5_5_DRAFT_EFFORT

    assert _outputs(fake_db)["models"]["draft"] == OPUS_5_5          # the default pipeline drafted it
    claude.queue(GOOD)

    body = refine().json()

    [call] = claude.calls
    assert (call["model"], call["output_config"]) == (OPUS_5_5, {"effort": OPUS_5_5_DRAFT_EFFORT})
    assert call["max_tokens"] == 500 + THINKING_ALLOWANCE_TOKENS
    assert body == {"rewritten_text": "Retrieval gets fast with pgvector.", "status": "ok", "message": "", "note": "",
                    "sources_used": "trace", "sources_message": ""}


def test_a_post_drafted_by_sonnet_is_rewritten_by_sonnet(claude, fake_db, seeded_kb, client, auth_headers):
    answer_pipeline(claude, [DRAFT])
    trace_id = _run("C")["trace_id"]
    claude.reset()
    claude.queue(GOOD)

    client.post("/refine-selection", headers=auth_headers(KB_USER),
                json={"selected_text": SELECTION, "instruction": "tighten", "full_post": POST, "trace_id": trace_id})

    [call] = claude.calls
    assert call["model"] == SONNET_4_6 and "output_config" not in call and call["max_tokens"] == 500


def test_the_prompt_has_the_stored_sources_block_the_style_rules_and_the_citation_rules(refine, claude, fake_db):
    from agents.draft_prompt import CITATION_RULES
    from utils.formatters import STYLE_RULES
    from utils.frames import SOURCES_ARE_DATA_RULE

    claude.queue(GOOD)
    refine(instruction="say it in one breath")

    prompt, outputs = _prompt(claude), _outputs(fake_db)
    assert outputs["draft_frame_block"] in prompt            # the block the drafter saw, rebuilt from the stored index
    assert '<source id="S1"' in prompt and "pgvector makes retrieval fast" in prompt
    assert SOURCES_ARE_DATA_RULE in prompt and CITATION_RULES in prompt
    assert STYLE_RULES.format(words_to_avoid="") in prompt
    assert "<instruction>\nsay it in one breath\n</instruction>" in prompt
    assert f"<selection>\n{SELECTION}\n</selection>" in prompt
    assert "[[R]] also covers what the author's instruction states" in prompt


def test_source_ids_come_from_the_stored_index_not_from_the_chunks_order(fake_db, post):
    """The index is the record of what S1 was. If it says S1 is the second
    stored chunk, the block shows the second chunk as S1."""
    from utils.frames import sources_block_from_index

    [trace] = fake_db.tables["generation_traces"]
    chunks = [{"text": "an unrelated first chunk", "source_type": "note"}, *trace["retrieved"]]
    index = {"S1": {**trace["node_outputs"]["source_index"]["S1"], "position": 1}}

    block = sources_block_from_index(index, chunks)

    assert block.count("<source ") == 1 and "pgvector makes retrieval fast" in block and "unrelated" not in block
    with pytest.raises(ValueError, match="points at chunk 5"):
        sources_block_from_index({"S1": {**index["S1"], "position": 5}}, chunks)


def test_an_index_that_points_outside_the_stored_chunks_is_a_409_not_a_guess(refine, claude, fake_db):
    [trace] = fake_db.tables["generation_traces"]
    trace["node_outputs"]["source_index"]["S1"]["position"] = 7

    resp = refine()

    assert resp.status_code == 409 and claude.calls == []


# --- The checks on the passage -----------------------------------------------------

@pytest.mark.parametrize("first,issue", [
    (INVENTED, "specific_not_in_cited_source"),                                  # a number its source does not state
    ("It was 40 percent faster, in my view. [[V]]", "view_contains_specific"),    # a specific in a view
    ("Retrieval gets fast with pgvector.", "uncited_span"),                      # no marker
    ("Retrieval gets fast with pgvector. [[S9]]", "citation_unknown_id"),        # an id that is not a source
    ("Retrieval gets fast with pgvector. [[source 1]]", "citation_malformed"),   # not a marker
    ("Retrieval gets fast — with pgvector. [[S1]]", None),                       # an em dash is normalised away, not an issue
])
def test_a_failed_check_is_retried_once_with_the_finding(refine, claude, fake_db, first, issue):
    claude.queue(first, GOOD)

    body = refine().json()

    assert (body["status"], body["rewritten_text"]) == ("ok", "Retrieval gets fast with pgvector.") if issue else True
    if issue is None:
        assert len(claude.calls) == 1 and "—" not in body["rewritten_text"]
        return
    assert len(claude.calls) == 2
    retry = _prompt(claude, 1)
    assert "YOUR PREVIOUS REWRITE WAS CHECKED AND NOT ACCEPTED" in retry and f"({issue})" in retry
    assert "What to do:" in retry and first in retry
    [record] = _refines(fake_db)
    assert record["status"] == "ok" and record["model"] == OPUS_5_5
    assert issue in record["attempts"][0]["checks"]["counts"] and record["attempts"][1]["checks"]["counts"] == {}
    assert [a["event_type"] for a in record["attempts"]] == ["refine_selection", "refine_selection_retry"]


def test_a_word_the_author_avoids_is_a_failed_check(refine, claude, fake_db):
    from memory.profile_store import save_profile

    save_profile({"name": "A", "words_to_avoid": ["leverage"]}, user_id=KB_USER)
    claude.queue("We leverage pgvector for fast retrieval. [[S1]]", GOOD)

    assert refine().json()["rewritten_text"] == "Retrieval gets fast with pgvector."
    assert list(_refines(fake_db)[0]["attempts"][0]["checks"]["counts"]) == ["banned_text"]


def test_two_failed_attempts_keep_the_selection_and_say_why(refine, claude, fake_db):
    claude.queue(INVENTED, INVENTED)

    body = refine().json()

    assert body == {"rewritten_text": SELECTION, "status": "reverted", "message": REVERTED, "note": "",
                    "sources_used": "trace", "sources_message": ""}
    assert len(claude.calls) == 2
    [record] = _refines(fake_db)
    assert record["status"] == "reverted" and len(record["attempts"]) == 2


def test_a_number_the_instruction_gives_may_be_cited_to_the_request(refine, claude):
    claude.queue("pgvector cut our p95 to 240 ms. [[R]]")

    body = refine(instruction="mention that our p95 is now 240 ms").json()

    assert (body["status"], body["rewritten_text"]) == ("ok", "pgvector cut our p95 to 240 ms.") and len(claude.calls) == 1


def test_the_note_is_returned_apart_from_the_text_and_a_note_alone_changes_nothing(refine, claude):
    claude.queue(GOOD + "\n<note>No source has an example; add one to your instruction.</note>",
                 "<note>No source has an example.</note>")

    first, second = refine().json(), refine().json()

    assert (first["rewritten_text"], first["note"]) == ("Retrieval gets fast with pgvector.",
                                                        "No source has an example; add one to your instruction.")
    assert (second["rewritten_text"], second["status"], second["note"]) == (SELECTION, "ok", "No source has an example.")


def test_the_markers_never_reach_the_author(refine, claude):
    claude.queue("Retrieval gets fast with pgvector. [[S1]] That is the argument. [[V]]")

    assert refine().json()["rewritten_text"] == "Retrieval gets fast with pgvector. That is the argument."


# --- Replies that cannot be used ------------------------------------------------------

def _reply(stop_reason: str, text: str = "") -> Message:
    details = RefusalStopDetails(type="refusal", category=None, explanation=None) if stop_reason == "refusal" else None
    return Message(id="msg", type="message", role="assistant", model=OPUS_5_5,
                   content=[TextBlock(type="text", text=text)] if text else [], stop_reason=stop_reason,
                   stop_sequence=None, stop_details=details, usage=Usage(input_tokens=10, output_tokens=10))


@pytest.mark.parametrize("stop_reason,text,says", [
    ("refusal", "", "declined"), ("max_tokens", "Retrieval gets fast with", "cut off"),
])
def test_a_refused_or_cut_off_rewrite_is_never_used(refine, claude, fake_db, stop_reason, text, says):
    claude.queue(_reply(stop_reason, text))

    body = refine().json()

    assert (body["status"], body["rewritten_text"]) == ("reverted", SELECTION) and says in body["message"]
    assert len(claude.calls) == 1 and _refines(fake_db)[0]["status"] == "reverted"


# --- Cost tracking ----------------------------------------------------------------------

def test_every_call_of_the_default_pipeline_and_of_refine_is_logged_with_its_exact_model_and_priced(
        claude, fake_db, seeded_kb, client, auth_headers, monkeypatch):
    import llm.client as llm_client
    from llm.pricing import PRICES, call_cost

    logged: list[dict] = []
    monkeypatch.setattr(llm_client, "schedule_usage_event", lambda **kw: logged.append(kw))
    answer_pipeline(claude, [DRAFT])
    trace_id = _run(None)["trace_id"]
    claude.reset()
    claude.queue(INVENTED, GOOD)
    client.post("/refine-selection", headers=auth_headers(KB_USER),
                json={"selected_text": SELECTION, "instruction": "tighten", "full_post": POST, "trace_id": trace_id})

    assert [(e["event_type"], e["model"]) for e in logged] == [
        ("generate", OPUS_5_5),                             # the default (D-Opus-low): no structure call
        ("refine_selection", OPUS_5_5), ("refine_selection_retry", OPUS_5_5)]
    assert {e["user_id"] for e in logged} == {KB_USER}
    for event in logged:
        assert event["model"] in PRICES
        assert call_cost(event["model"], event["input_tokens"], event["output_tokens"]) > 0
