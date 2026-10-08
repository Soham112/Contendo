"""Archetypes are structure only, and the sources decide which ones are allowed."""

import json
import re

import pytest

from tests.conftest import ARCHETYPE_GENERAL
from tests.generation_fixtures import (
    ARTICLE, BURNOUT, INVESTOR_UPDATE, OBSERVED, OWN, STORY, last_prompt, make_state,
)


# --- Archetypes: allowed by the sources ---------------------------------------------------------

STORY = {"incident_report", "personal_story", "before_after"}


def test_archetype_blocks_describe_structure_only():
    from utils.formatters import ARCHETYPES, GENERAL_ARCHETYPE, STORY_ARCHETYPES

    assert STORY_ARCHETYPES == STORY and GENERAL_ARCHETYPE in ARCHETYPES
    for key, archetype in ARCHETYPES.items():
        block = archetype.structure
        assert not re.search(r"\d+\s*[–-]\s*\d+ words|LinkedIn:|Thread:|Article:", block), key
        assert "iagram" not in block, key
        for demand in ("must be dated or located", "name the tool", "2–3 pieces of concrete evidence"):
            assert demand not in block, key


def test_allowed_archetypes_follow_the_sources():
    from agents.archetype_agent import allowed_archetypes

    assert set(allowed_archetypes("opinion", 0)) == {"contrarian_take", "teach_me_something", "general"}
    learned = set(allowed_archetypes("learned", 0))
    assert not (learned & STORY) and {"general", "prediction_bet", "list_that_isnt"} <= learned
    assert STORY <= set(allowed_archetypes("experience", 1))
    assert STORY <= set(allowed_archetypes("mixed", 2))


def _choose(claude, state, reply):
    from agents.archetype_agent import choose_archetype

    claude.queue(reply)
    return choose_archetype(state)


def test_story_archetype_is_never_offered_without_a_self_authored_chunk(claude):
    decision = _choose(claude, make_state([ARTICLE], tone="storytelling"), ARCHETYPE_GENERAL)

    options = last_prompt(claude).split("Post types you may choose from", 1)[1]
    for key in STORY:
        assert f"- {key}:" not in options
    assert not (set(decision["allowed"]) & STORY)
    assert "storytelling" not in last_prompt(claude)  # tone is not an input to the choice
    assert claude.calls[0]["max_tokens"] == 100


def _story(note=1, quote=OWN["text"], archetype="before_after") -> str:
    return json.dumps({"archetype": archetype, "event_note": note, "event_quote": quote})


def test_story_archetype_is_kept_when_the_quote_is_in_the_cited_own_note(claude):
    state = make_state([OWN, ARTICLE])
    kept = _choose(claude, state, _story())

    assert kept["archetype"] == "before_after" and kept["downgraded_from"] is None
    assert kept["event_note"] == 1 and kept["event_quote"] == OWN["text"]
    prompt = last_prompt(claude)
    assert f"[1]\n{OWN['text']}" in prompt
    assert "youtube on statistics" in prompt and ARTICLE["text"] not in prompt
    assert OWN["source_title"] not in prompt and ARTICLE["source_title"] not in prompt  # no titles
    assert "copy one sentence from that note, word for word" in prompt


@pytest.mark.parametrize("quote", [
    "we rebuilt the ranker in march and latency fell.",        # case
    "We rebuilt the ranker\n   in March and  latency fell.",    # whitespace
    "rebuilt the ranker in March",                              # part of the sentence
])
def test_quote_check_ignores_only_case_and_whitespace(claude, quote):
    assert _choose(claude, make_state([OWN]), _story(quote=quote))["archetype"] == "before_after"


@pytest.mark.parametrize("reply,reason", [
    (json.dumps({"archetype": "before_after"}), "without an own note"),
    (_story(note=2), "without an own note"),                   # only one own note exists
    (_story(note=0), "without an own note"),
    (_story(quote=None), "event quote is not in the cited own note"),
    (_story(quote=""), "event quote is not in the cited own note"),
    (_story(quote="We rebuilt the ranker in April and latency fell."), "event quote is not in the cited own note"),
    (_story(quote="We rebuilt the ranker in March, and latency fell."), "event quote is not in the cited own note"),
    (_story(quote=ARTICLE["text"]), "event quote is not in the cited own note"),  # a real sentence, wrong source
    (_story(quote="the ranker"), "event quote is not in the cited own note"),     # a fragment, not a sentence
])
def test_story_archetype_is_downgraded_when_the_event_is_not_verified(claude, caplog, reply, reason):
    with caplog.at_level("WARNING", logger="agents.archetype_agent"):
        decision = _choose(claude, make_state([OWN, ARTICLE]), reply)

    assert decision["archetype"] == "general"
    assert decision["chosen"] == "before_after" and decision["downgraded_from"] == "before_after"
    assert reason in decision["reason"] and reason in caplog.text
    sent = json.loads(reply)
    assert decision["event_note"] == sent.get("event_note")    # what the model cited is kept in the record
    assert decision["event_quote"] == sent.get("event_quote")


def test_external_notes_are_never_numbered_so_they_cannot_be_cited(claude):
    """A story type can only cite a self-authored note: observations and articles get no number."""
    decision = _choose(claude, make_state([OBSERVED, OWN, ARTICLE]), _story(note=2, quote=OBSERVED["text"]))

    prompt = last_prompt(claude)
    assert f"[1]\n{OWN['text']}" in prompt and "[2]" not in prompt
    assert OBSERVED["text"] not in prompt
    assert decision["archetype"] == "general"


def _founder_06_state():
    return make_state([BURNOUT, INVESTOR_UPDATE], topic="Noticing burnout before it runs you",
                      context="Keep it practical, no therapy-speak", tone="storytelling", length="concise")


def test_founder_06_template_cited_for_the_burnout_story_is_downgraded(claude):
    """The model cites note 1 (the investor-update template, the only self-authored note) as the
    event behind a burnout story, quoting the burnout note. The quote is not in note 1."""
    state = _founder_06_state()
    assert state["perspective"] == "mixed"

    decision = _choose(claude, state, _story(quote="Last spring I burned out without noticing."))

    assert decision["archetype"] == "general"
    assert decision["downgraded_from"] == "before_after"
    assert decision["reason"] == "story type whose event quote is not in the cited own note"
    assert decision["event_note"] == 1
    prompt = last_prompt(claude)
    assert "[1]\nThe monthly investor update I send" in prompt and "burned out" not in prompt


def test_founder_06_a_real_sentence_from_the_template_still_passes_the_check(claude):
    """Known limit: the code proves the sentence is in the cited note. Whether that sentence is
    the event the post is about is the model's judgement."""
    quote = ("Since Saltmarsh Labs started sending this format, the number of useful intros from "
             "investors went from about one a quarter to three a month.")
    decision = _choose(claude, _founder_06_state(), _story(quote=quote))
    assert decision["archetype"] == "before_after"


def test_a_type_the_sources_do_not_allow_becomes_general(claude, caplog):
    with caplog.at_level("WARNING", logger="agents.archetype_agent"):
        decision = _choose(claude, make_state([ARTICLE]), _story(archetype="personal_story"))

    assert decision["archetype"] == "general"
    assert decision["chosen"] == "personal_story" and decision["downgraded_from"] == "personal_story"
    assert "personal_story" in caplog.text


@pytest.mark.parametrize("reply", ["incident_report", "not json at all", '{"archetype": 7}', '{"wrong": "key"}'])
def test_failed_or_junk_inference_falls_back_to_general_and_is_logged(claude, caplog, reply):
    from agents.archetype_agent import choose_archetype

    claude.queue(reply, reply)  # the structured call retries once before giving up
    with caplog.at_level("WARNING", logger="agents.archetype_agent"):
        decision = choose_archetype(make_state([OWN]))

    assert len(claude.calls) == 2
    assert decision["archetype"] == "general"
    assert decision["chosen"] is None and "inference failed" in decision["reason"]
    assert "inference failed" in caplog.text


def test_api_error_during_inference_also_falls_back_to_general(claude):
    from agents.archetype_agent import choose_archetype

    def boom(kwargs):
        raise RuntimeError("anthropic down")

    claude.respond_with(boom)
    assert choose_archetype(make_state([OWN]))["archetype"] == "general"


def test_draft_node_records_the_decision_and_uses_the_general_block(claude):
    from agents.draft_agent import draft_node

    claude.queue('{"archetype": "personal_story"}', "The draft.")
    state = draft_node(make_state([OWN]))

    assert state["archetype"] == "general"
    assert state["archetype_decision"]["downgraded_from"] == "personal_story"
    assert "write this post as a General Post" in last_prompt(claude)
    assert "leave out any section the sources cannot fill" in last_prompt(claude)


def test_unknown_stored_archetype_key_gets_the_general_block():
    from utils.formatters import ARCHETYPES, get_archetype

    assert get_archetype("no_such_type") is ARCHETYPES["general"]
    assert get_archetype("") is ARCHETYPES["general"]
