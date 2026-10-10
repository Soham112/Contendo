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
