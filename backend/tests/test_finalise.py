"""finalise(): the last thing that touches a post's text in every variant. The
record it returns is of exactly the string it returns."""

import pytest

from utils.formatters import count_words, resolve_length_target


# --- finalise: one function, the record is of the string it returns ------------------

def test_finalise_normalises_then_measures_the_normalised_text():
    from pipeline.finalise import finalise

    target = resolve_length_target("linkedin post", "standard", first_post=True)
    text = " ".join(["word"] * 99) + " alpha—beta"
    assert count_words(text) == 100

    finalised = finalise(text, target)

    assert finalised.text.endswith("alpha, beta")
    assert finalised.record == {
        "words": 101, "target": {"min_words": 70, "max_words": 100, "basis": "first_post"},
        "length": "over_length", "over_by": 1, "under_by": 0,
        "leftover_markers": [], "em_dashes_remaining": 0,
    }
    assert finalised.record["words"] == count_words(finalised.text)


@pytest.mark.parametrize("words,length,over_by,under_by", [
    (250, "ok", 0, 0), (350, "ok", 0, 0), (351, "over_length", 1, 0), (249, "under_length", 0, 1), (3, "under_length", 0, 247),
])
def test_the_record_says_how_far_over_or_under(words, length, over_by, under_by):
    from pipeline.finalise import finalise

    record = finalise(" ".join(["word"] * words), resolve_length_target("linkedin post", "standard")).record

    assert (record["words"], record["length"], record["over_by"], record["under_by"]) == (words, length, over_by, under_by)


def test_a_thin_sources_target_has_no_floor_and_a_thread_has_no_target():
    from pipeline.finalise import finalise

    thin = finalise("Three words only.", resolve_length_target("linkedin post", "standard", thin_sources=True)).record
    thread = finalise("1/ A tweet.", resolve_length_target("thread", "standard")).record

    assert (thin["length"], thin["under_by"]) == ("ok", 0)
    assert (thread["length"], thread["target"], thread["words"]) == ("no_target", None, 3)


def test_leftover_markers_and_protected_em_dashes_are_recorded_not_removed():
    from pipeline.finalise import finalise

    text = "A stray marker. [S2]\n\n```\ncode — untouched [[S1]]\n```\n\nAnother [[V]] here."

    finalised = finalise(text, None)

    assert finalised.text == text
    assert [(m["kind"], m["text"]) for m in finalised.record["leftover_markers"]] == [
        ("single_brackets", "[S2]"), ("leftover", "[[V]]")]
    assert finalised.record["em_dashes_remaining"] == 0   # the one em dash is inside code


def test_finalise_is_idempotent():
    from pipeline.finalise import finalise

    once = finalise("Fast—really fast. It held — mostly. Pages 3—5.", None)

    assert finalise(once.text, None) == once


def test_finalise_marked_gives_spans_that_index_the_returned_text():
    from pipeline.finalise import finalise_marked

    finalised, stripped = finalise_marked("It was fast — really fast. [[S1]] Then it held—mostly. [[V]]", None)

    assert finalised.text == "It was fast, really fast. Then it held, mostly."
    assert [finalised.text[s.start:s.end] for s in stripped.spans] == ["It was fast, really fast.", "Then it held, mostly."]
    assert finalised.record["words"] == count_words(finalised.text)
    assert finalised.record["em_dashes_remaining"] == 0


# --- Length is the post's prose (variants B and C) ---------------------------------

# The first draft of the 6d live run on pm-09: 239 words counting every token, 52 of them the
# [DIAGRAM: ...] line. That line pushed the post over its 180-word maximum and into a full redraft.
PM09_6D = """Most product teams jump straight from "what do we want to achieve?" to "here's what we'll build." [[V]]

That's the gap an opportunity solution tree is designed to close. [[S1]]

Think of it like a family tree, but for your product thinking. One outcome sits at the top. Beneath it, customer needs and pains branch out. Beneath those, possible solutions. Beneath those, small experiments to test each one. [[S1]]

The structure forces a stop. You can't draw a line from outcome to solution without asking what customer problem sits in between. [[S1]]

Here's the thing I find most useful about it: it makes gaps embarrassingly visible. [[V]] If you've got five solutions mapped under one opportunity and zero under the rest, that's not a strategy, it's a fixation. [[S1]]

Where it gets messy is maintenance. A notes piece on this kind of framework warns it can turn into a wall of sticky notes that nobody looks at after week two. [[S1]] One way around that: keep it to a single outcome per quarter. [[S1]]

One outcome. Real discipline. [[V]]

What's the gap between your current outcome and your next solution that you haven't actually named yet? [[V]]

[DIAGRAM: Vertical tree diagram with "Desired Outcome" at the top; second level shows three "Opportunity" nodes (customer needs, pains, desires); third level shows "Solution" nodes branching from each Opportunity, with one Opportunity having multiple Solutions and two Opportunities having none, highlighted to show imbalance; fourth level shows "Experiment" nodes beneath each Solution]"""
CONCISE = {"min_words": 100, "max_words": 180, "may_expand": True, "basis": "length_setting"}


def test_the_6d_pm_09_draft_is_measured_without_its_diagram_line():
    from pipeline.finalise import finalise_marked, validation_record
    from utils.citations import prose_word_count, strip_citations
    from utils.formatters import count_words

    clean = strip_citations(PM09_6D).text
    diagram = clean.split("\n\n")[-1]
    assert (count_words(clean), count_words(diagram)) == (239, 52)

    assert prose_word_count(clean) == prose_word_count(PM09_6D) == 187         # with or without its markers
    finalised, _ = finalise_marked(PM09_6D, CONCISE)
    assert (finalised.record["words"], finalised.record["over_by"]) == (187, 7)     # not 239 and 59
    assert diagram in finalised.text                                           # not counted, and not removed
    # Pipeline A's record still counts every token.
    assert validation_record(clean, CONCISE)["words"] == 239


def test_headings_placeholders_and_code_blocks_are_not_prose_and_inline_code_is():
    from utils.citations import prose_word_count

    post = ("## A heading of five words\n\n"
            "We ran `make deploy` twice that day.\n\n"
            "```python\nprint('five words in this block')\n```\n\n"
            "[IMAGE: a photo of the whiteboard]\n\n"
            "It passed.")
    assert prose_word_count(post) == 7 + 2
    assert prose_word_count("") == 0


def test_the_trim_measures_prose_so_a_placeholder_is_never_a_reason_to_trim(claude):
    from agents.trim_agent import trim_node
    from pipeline.finalise import finalise_draft_node
    from tests.generation_fixtures import OWN, make_state

    diagram = "[DIAGRAM: " + " ".join(["box"] * 30) + "]"
    marked = "\n\n".join([*(f"Plain sentence {'word ' * 7}here. [[V]]" for _ in range(11)), diagram])    # 110 words of prose
    state = finalise_draft_node(make_state([OWN], archetype="general", current_draft=marked, length_target={
        "min_words": 70, "max_words": 100, "may_expand": False, "basis": "first_post"}))
    claude.queue('{"ranking": [3, 5, 7]}')

    state = trim_node(state)

    result = state["trim_result"]
    assert (result["words_before"], result["words_after"], len(result["deleted"])) == (110, 100, 1)
    assert diagram in state["current_draft"]
