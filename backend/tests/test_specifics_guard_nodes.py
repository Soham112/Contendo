"""The specifics guard in humanizer_node and predictability_audit_node.

A rewrite may not add or change facts. If it does, the node retries once with
the violations listed; if the retry still adds facts, the node keeps its input.
Texts are from real eval runs (ds-08, pm-07).
"""

import pytest

USER = "user-guard"

CHUNK = (
    "Incident note. An upstream booking team renamed a column from booking_ts to booked_at. "
    "For six days Kestrel saw zero recent bookings for one region."
)
DRAFT = "An upstream team renamed one column. For six days the forecast saw zero bookings."
FABRICATED = "Our Thursday afternoon volume runs 34% above baseline. For six days the forecast saw zero bookings."
CLEAN_REWRITE = "One renamed column. Six days of zero bookings, and nobody noticed."


def _state(**overrides):
    state = {
        "quality": "standard",
        "user_id": USER,
        "topic": "Data contracts",
        "context": "",
        "format": "thread",  # no word-count rule in the prompt
        "length": "standard",
        "profile": {"name": "Mara", "role": "Data scientist", "bio": "Seven years in data science"},
        "retrieval_bundle": {"chunks": [{"text": CHUNK}]},
        "retrieved_chunks": [],
        "critic_brief": {},
        "current_draft": DRAFT,
        "iterations": 0,
        "draft_history": [],
    }
    state.update(overrides)
    return state


def _prompt(call):
    return call["messages"][-1]["content"]


# --- humanizer -------------------------------------------------------------------

def test_humanizer_clean_rewrite_needs_one_call(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue(CLEAN_REWRITE)
    state = humanizer_node(_state())

    assert len(claude.calls) == 1
    assert state["current_draft"] == CLEAN_REWRITE
    assert state.get("specifics_guard", []) == []
    assert [d["node"] for d in state["draft_history"]] == ["humanizer"]


def test_humanizer_prompt_states_facts_are_fixed(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue(CLEAN_REWRITE)
    humanizer_node(_state())
    prompt = _prompt(claude.calls[0])
    assert "Facts are fixed." in prompt
    assert "Never add or change any number" in prompt
    assert "the last startup I advised" not in prompt
    assert "Your previous attempt" not in prompt


def test_humanizer_retries_with_violations_and_accepts_a_clean_retry(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue(FABRICATED, CLEAN_REWRITE)
    state = humanizer_node(_state())

    assert [c["model"] for c in claude.calls] == ["claude-sonnet-4-6"] * 2
    retry_prompt = _prompt(claude.calls[1])
    assert "Your previous attempt added or changed these details" in retry_prompt
    assert "- Thursday" in retry_prompt and "- 34%" in retry_prompt
    assert state["current_draft"] == CLEAN_REWRITE
    assert state["specifics_guard"] == [{
        "node": "humanizer", "iteration": 1,
        "first_attempt": [{"text": "Thursday", "kind": "weekday"}, {"text": "34%", "kind": "percent"}],
        "retry": [], "outcome": "accepted_after_retry",
    }]
    assert [(d["node"], d["text"]) for d in state["draft_history"]] == [("humanizer", CLEAN_REWRITE)]


def test_humanizer_keeps_its_input_when_the_retry_still_adds_facts(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue(FABRICATED, "Review comments jumped 60% that first month.")
    state = humanizer_node(_state())

    assert len(claude.calls) == 2
    assert state["current_draft"] == DRAFT
    assert state["draft_history"] == []          # no rewrite recorded
    assert state["iterations"] == 1              # still counts, so the polished loop ends
    entry = state["specifics_guard"][0]
    assert entry["outcome"] == "reverted"
    assert [v["text"] for v in entry["retry"]] == ["60%", "first month"]


def test_humanizer_strips_a_printed_word_count_without_retrying(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue(CLEAN_REWRITE + "\n\nWord count: 295")
    state = humanizer_node(_state())
    assert len(claude.calls) == 1
    assert state["current_draft"] == CLEAN_REWRITE


def test_humanizer_skips_draft_quality(claude):
    from agents.humanizer_agent import humanizer_node

    state = humanizer_node(_state(quality="draft"))
    assert claude.calls == []
    assert state["current_draft"] == DRAFT


# --- predictability audit --------------------------------------------------------

AUDIT_INPUT = "An upstream team renamed one column. For six days the forecast saw zero bookings."
FLAGGED = "An upstream team renamed one column."


def test_audit_clean_result_needs_no_retry(claude):
    from agents.predictability_audit_agent import predictability_audit_node

    claude.queue(FLAGGED, "One column, renamed.", "One column, renamed. For six days the forecast saw zero bookings.")
    state = predictability_audit_node(_state(current_draft=AUDIT_INPUT, iterations=1))

    assert [c["model"] for c in claude.calls] == ["claude-haiku-4-5-20251001", "claude-sonnet-4-6",
                                                  "claude-haiku-4-5-20251001"]
    assert state["current_draft"] == "One column, renamed. For six days the forecast saw zero bookings."
    assert state.get("specifics_guard", []) == []


def test_audit_retries_steps_two_and_three_and_accepts_a_clean_retry(claude):
    from agents.predictability_audit_agent import predictability_audit_node

    claude.queue(
        FLAGGED,                                                         # step 1
        "On a Thursday, someone renamed a column.",                      # step 2 adds a weekday
        "On a Thursday, someone renamed a column. For six days the forecast saw zero bookings.",  # step 3
        "Someone renamed a column.",                                     # step 2 retry
        "Someone renamed a column. For six days the forecast saw zero bookings.",  # step 3 retry
    )
    state = predictability_audit_node(_state(current_draft=AUDIT_INPUT, iterations=1))

    assert len(claude.calls) == 5  # step 1 is not repeated
    assert "- Thursday" in _prompt(claude.calls[3]) and "- Thursday" in _prompt(claude.calls[4])
    assert state["current_draft"] == "Someone renamed a column. For six days the forecast saw zero bookings."
    assert state["specifics_guard"][0]["node"] == "predictability_audit"
    assert state["specifics_guard"][0]["outcome"] == "accepted_after_retry"


def test_audit_keeps_its_input_when_the_retry_still_alters_a_figure(claude):
    from agents.predictability_audit_agent import predictability_audit_node

    # The burstiness step turns "six days" into "nine days", twice.
    claude.queue("CLEAN", "For nine days nothing. One renamed column.", "For nine days nothing. One renamed column.")
    state = predictability_audit_node(_state(current_draft=AUDIT_INPUT, iterations=1))

    assert len(claude.calls) == 3  # CLEAN: step 3 and its retry only
    assert state["current_draft"] == AUDIT_INPUT
    entry = state["specifics_guard"][0]
    assert entry["outcome"] == "reverted"
    assert entry["first_attempt"] == [{"text": "nine days", "kind": "duration"}]


def test_audit_prompts_forbid_adding_or_removing_figures(claude):
    from agents.predictability_audit_agent import predictability_audit_node

    claude.queue(FLAGGED, "One column, renamed.", AUDIT_INPUT)
    predictability_audit_node(_state(current_draft=AUDIT_INPUT, iterations=1))
    assert "Add none and remove none." in _prompt(claude.calls[1])
    assert "more specific" not in _prompt(claude.calls[1])
    assert "Add none and remove none." in _prompt(claude.calls[2])


# --- finalize ------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "The post.\n\nWord count: 295",
    "The post.\nword count 310 words",
    "  WORD COUNT: 12\nThe post.",
])
def test_finalize_strips_word_count_lines(text):
    from pipeline.graph import finalize_node

    state = finalize_node({"current_draft": text})
    assert "word count" not in state["final_post"].lower()
    assert "The post." in state["final_post"]


def test_finalize_keeps_prose_that_mentions_word_count():
    from pipeline.graph import finalize_node

    text = "Nobody cares about word count. They care whether it is true."
    assert finalize_node({"current_draft": text})["final_post"] == text


# --- word count enforcer ---------------------------------------------------------

SHORT_POST = DRAFT  # well under 250 words for a standard LinkedIn post -> expand
LONG_POST = " ".join([DRAFT] * 30)  # over 350 words -> trim


def _enforcer_state(post):
    return _state(format="linkedin post", length="standard", current_draft=post, iterations=1)


def test_enforcer_expand_prompt_uses_only_existing_material(claude):
    from agents.word_count_enforcer_agent import word_count_enforcer_node

    claude.queue(DRAFT + " That is why the contract matters.")
    word_count_enforcer_node(_enforcer_state(SHORT_POST))
    prompt = _prompt(claude.calls[0])
    assert "Add one specific detail" not in prompt
    assert "Expand only with material already in the post" in prompt
    assert "Never add or change any number" in prompt


def test_enforcer_clean_expansion_needs_no_retry(claude):
    from agents.word_count_enforcer_agent import word_count_enforcer_node

    expanded = DRAFT + " Nobody noticed, which is the real problem."
    claude.queue(expanded)
    state = word_count_enforcer_node(_enforcer_state(SHORT_POST))
    assert len(claude.calls) == 1
    assert state["current_draft"] == expanded
    assert state.get("specifics_guard", []) == []


def test_enforcer_retries_an_expansion_that_adds_facts(claude):
    from agents.word_count_enforcer_agent import word_count_enforcer_node

    clean = DRAFT + " Nobody noticed."
    claude.queue(DRAFT + " It cost us 34% of a quarter's margin.", clean)
    state = word_count_enforcer_node(_enforcer_state(SHORT_POST))

    assert len(claude.calls) == 2
    assert "- 34%" in _prompt(claude.calls[1])
    assert state["current_draft"] == clean
    assert state["specifics_guard"][0]["node"] == "word_count_enforcer"
    assert state["specifics_guard"][0]["outcome"] == "accepted_after_retry"


def test_enforcer_keeps_its_input_when_the_retry_still_adds_facts(claude):
    from agents.word_count_enforcer_agent import word_count_enforcer_node

    claude.queue(DRAFT + " Every Thursday it happens.", DRAFT + " Every Thursday it happens again.")
    state = word_count_enforcer_node(_enforcer_state(SHORT_POST))
    assert state["current_draft"] == SHORT_POST
    assert state["specifics_guard"][0]["outcome"] == "reverted"
    assert state["draft_history"] == []


def test_enforcer_guards_trimming_too(claude):
    from agents.word_count_enforcer_agent import word_count_enforcer_node

    # The trim turns "six days" into "nine days", twice.
    claude.queue("For nine days the forecast saw zero bookings.", "For nine days, zero bookings.")
    state = word_count_enforcer_node(_enforcer_state(LONG_POST))
    assert state["current_draft"] == LONG_POST
    assert state["specifics_guard"][0]["first_attempt"] == [{"text": "nine days", "kind": "duration"}]


def test_enforcer_strips_a_printed_word_count(claude):
    from agents.word_count_enforcer_agent import word_count_enforcer_node

    claude.queue(DRAFT + " Nobody noticed.\n\nWord count: 262")
    state = word_count_enforcer_node(_enforcer_state(SHORT_POST))
    assert len(claude.calls) == 1
    assert state["current_draft"] == DRAFT + " Nobody noticed."
