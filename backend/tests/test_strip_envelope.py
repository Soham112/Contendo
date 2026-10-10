"""The strip and finalise steps of the single-writer pipeline (pipeline/finalise.py):
reading the draft's output envelope, removing the markers, and what is recorded.
The drafter and its prompt are in test_single_writer_draft.py."""

import pytest

from tests.generation_fixtures import ARTICLE, OWN, enveloped, make_state
from tests.test_single_writer_draft import EVENT, STORY_KEY, _output

def _finalise(state):
    from pipeline.finalise import finalise_draft_node, strip_draft_node

    return finalise_draft_node(strip_draft_node(state))


def _strip(marked: str, archetype: str, **decision):
    """strip (the envelope) then finalise (markers), as the graph runs them."""
    from pipeline.finalise import finalise_draft_node, strip_draft_node

    state = make_state([OWN, ARTICLE], archetype=archetype, current_draft=enveloped(marked),
                       archetype_decision={"archetype": archetype, "chosen": archetype, "allowed": [archetype, "general"],
                                           "downgraded_from": None, "reason": None, **decision})
    return finalise_draft_node(strip_draft_node(state))


def test_strip_alone_reads_the_envelope_and_leaves_the_markers():
    from pipeline.finalise import strip_draft_node

    state = strip_draft_node(make_state([OWN], archetype=STORY_KEY,
                                        current_draft=_output("We rebuilt the ranker. [[S1]]", EVENT)))

    assert state["current_draft"] == "We rebuilt the ranker. [[S1]]"
    assert state["event"]["status"] == "cited"
    assert "final_post" not in state


def test_strip_removes_markers_and_the_envelope_and_records_both():
    state = _strip(_output("We rebuilt the ranker in March. [[S1]]\n\nThe talk agrees. [[S2]] So do I. [[V]]", EVENT), STORY_KEY)

    assert state["final_post"] == "We rebuilt the ranker in March.\n\nThe talk agrees. So do I."
    assert state["current_draft"] == state["final_post"]
    assert state["event"] == {"status": "cited", "source": "S1",
                              "quote": "We rebuilt the ranker in March and latency fell.", "line": EVENT}
    assert [(c["text"], c["basis"], c["sources"]) for c in state["citations"]] == [
        ("We rebuilt the ranker in March.", "sources", ["S1"]),
        ("The talk agrees.", "sources", ["S2"]),
        ("So do I.", "view", []),
    ]
    for c in state["citations"]:
        assert state["final_post"][c["start"]:c["end"]] == c["text"]
    assert state["citation_failures"] == []
    assert state["archetype"] == STORY_KEY


def test_event_none_makes_the_post_general_and_the_decision_says_why():
    state = _strip(_output("Most teams skip this. [[V]]", "none"), STORY_KEY)

    assert state["final_post"] == "Most teams skip this."
    assert state["event"]["status"] == "none"
    assert state["archetype"] == "general"
    assert state["archetype_decision"]["archetype"] == "general"
    assert state["archetype_decision"]["downgraded_from"] == STORY_KEY
    assert state["archetype_decision"]["chosen"] == STORY_KEY
    assert state["archetype_decision"]["reason"]


@pytest.mark.parametrize("marked,status", [
    (_output("We rebuilt the ranker. [[S1]]"), "missing"),
    (_output("We rebuilt the ranker. [[S1]]", "the rebuild"), "malformed"),
])
def test_a_failed_event_is_recorded_and_never_reaches_the_post(marked, status):
    state = _strip(marked, STORY_KEY)

    assert state["event"]["status"] == status
    assert state["final_post"] == "We rebuilt the ranker."
    assert state["archetype"] == STORY_KEY  # acting on the failure is for the checks, not this step


def test_a_draft_with_no_post_tag_is_kept_whole_and_the_missing_tag_is_recorded():
    # The fallback, on purpose: a draft that ignored the envelope is not thrown away.
    from pipeline.finalise import finalise_draft_node, strip_draft_node

    written = "Most teams skip this. [[V]]\n\nWe did not. [[S1]]"
    state = make_state([OWN], archetype="general", current_draft=written,
                       draft_history=[{"node": "draft", "iteration": 0, "text": written}])

    state = finalise_draft_node(strip_draft_node(state))

    assert state["final_post"] == "Most teams skip this.\n\nWe did not."
    assert state["draft_format"] == [{"draft": "draft", "kind": "post_tag_missing", "text": ""}]


def test_text_outside_the_envelope_never_reaches_the_post_and_is_recorded():
    # The 6b live run on pm-01: a "---" line between the event and the post reached the author.
    written = f"<event>{EVENT}</event>\n\n---\n\n<post>\nWe rebuilt the ranker. [[S1]]\n</post>\n\nHope this helps."
    state = make_state([OWN], archetype=STORY_KEY, current_draft=written,
                       draft_history=[{"node": "draft", "iteration": 0, "text": written}])

    state = _finalise(state)

    assert state["final_post"] == "We rebuilt the ranker."
    assert state["draft_format"] == [{"draft": "draft", "kind": "text_outside_tags", "text": "---"},
                                     {"draft": "draft", "kind": "text_outside_tags", "text": "Hope this helps."}]
    assert state["event"]["status"] == "cited"


def test_a_well_formed_draft_records_no_format_failure():
    assert "draft_format" not in _strip(_output("Most teams skip this. [[V]]"), "general")


def test_marker_failures_are_recorded_with_where_they_were():
    state = _strip("A cited line. [[S1]]\nA line with a bad marker. [[S1 and S2]]\nA line with none.", "general")

    assert state["final_post"] == "A cited line.\nA line with a bad marker.\nA line with none."
    assert [(f["kind"], f["text"]) for f in state["citation_failures"]] == [("malformed", "[[S1 and S2]]")]
    assert [c["basis"] for c in state["citations"]] == ["sources", "uncited", "uncited"]
    assert state["event"]["status"] == "absent"
