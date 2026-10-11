"""The drafter's output envelope and the targeted-fix format (utils/draft_output.py):
what is read from the tags, and what is dropped and recorded."""

import pytest

from utils.draft_output import Fix, parse_draft_output, parse_fixes

QUOTE = "Only 38 percent of new clinics finished setup within 14 days."
POST = "Nine steps were too many. [[S1]]\n\nWe cut five. [[S1]]"


def _kinds(output) -> list[str]:
    return [failure["kind"] for failure in output.format_failures]


# --- The post ------------------------------------------------------------------------

def test_the_post_is_what_stands_between_the_post_tags():
    output = parse_draft_output(f"<post>\n{POST}\n</post>", story=False)

    assert (output.body, output.status, output.line, output.format_failures) == (POST, "absent", "", ())


def test_the_6b_pm_01_output_with_a_stray_separator_gives_a_post_without_it():
    # Step 6b's live run: the drafter wrote "---" between the event and the post, and it reached the author.
    written = f'<event>S1 | "{QUOTE}"</event>\n\n---\n\n<post>\n{POST}\n</post>'

    output = parse_draft_output(written, story=True)

    assert output.body == POST and "---" not in output.body
    assert output.format_failures == ({"kind": "text_outside_tags", "text": "---"},)
    assert (output.status, output.source, output.quote) == ("cited", "S1", QUOTE)


@pytest.mark.parametrize("written,stray", [
    (f"Here is the post:\n\n<post>{POST}</post>", ["Here is the post:"]),
    (f"<post>{POST}</post>\n\nLet me know if you want changes.", ["Let me know if you want changes."]),
    (f"Sure.\n<post>{POST}</post>\nDone.", ["Sure.", "Done."]),
])
def test_text_outside_the_tags_is_dropped_and_recorded(written, stray):
    output = parse_draft_output(written, story=False)

    assert output.body == POST
    assert [(f["kind"], f["text"]) for f in output.format_failures] == [("text_outside_tags", text) for text in stray]


def test_whitespace_around_the_tags_is_not_a_failure():
    assert parse_draft_output(f"\n\n  <post>\n\n{POST}\n\n</post>\n", story=False).format_failures == ()


def test_a_post_with_no_closing_tag_runs_to_the_end_and_says_so():
    output = parse_draft_output(f"<post>\n{POST}", story=False)

    assert output.body == POST and _kinds(output) == ["post_unclosed"]


def test_with_no_post_tag_everything_outside_the_event_is_the_post_and_it_is_recorded():
    output = parse_draft_output(f'<event>none</event>\n\n{POST}', story=True)

    assert output.body == POST and _kinds(output) == ["post_tag_missing"] and output.status == "none"


def test_an_event_tag_inside_the_post_is_part_of_the_post():
    output = parse_draft_output("<post>We write <event>none</event> in docs. [[V]]</post>", story=False)

    assert (output.status, output.body) == ("absent", "We write <event>none</event> in docs. [[V]]")


# --- The event -------------------------------------------------------------------------

@pytest.mark.parametrize("event,source,quote", [
    ('S3 | "We cut the form to four steps."', "S3", "We cut the form to four steps."),
    ('  S12 |"We cut the form."  ', "S12", "We cut the form."),
    ("S1 | “We cut the form.”", "S1", "We cut the form."),
    ('S1 | "She said "ship it" and we did."', "S1", 'She said "ship it" and we did.'),
])
def test_an_event_gives_the_source_and_the_quote(event, source, quote):
    output = parse_draft_output(f"<event>{event}</event>\n<post>{POST}</post>", story=True)

    assert (output.status, output.source, output.quote, output.failed) == ("cited", source, quote, False)
    assert output.line == event.strip() and output.body == POST


def test_event_none_is_an_answer_not_a_failure():
    output = parse_draft_output(f"<event>none</event>\n<post>{POST}</post>", story=True)

    assert (output.status, output.failed, output.line, output.format_failures) == ("none", False, "none", ())


@pytest.mark.parametrize("event", [
    "", "S3", 'S3 "no pipe"', "S3 | no quotes", 'S3 | ""', 's3 | "lower case id"', 'S0 | "no such id"',
    'S1,S2 | "two sources"', "None", 'none | "extra"', 'S3 | "quote" and then more',
])
def test_a_malformed_event_is_a_failure_and_never_reaches_the_post(event):
    output = parse_draft_output(f"<event>{event}</event>\n<post>{POST}</post>", story=True)

    assert (output.status, output.failed, output.body) == ("malformed", True, POST)


def test_a_story_without_an_event_is_a_failure_and_other_posts_need_none():
    assert parse_draft_output(f"<post>{POST}</post>", story=True).status == "missing"
    assert parse_draft_output(f"<post>{POST}</post>", story=False).status == "absent"


def test_an_event_on_a_post_type_that_takes_none_is_a_failure():
    output = parse_draft_output(f"<event>none</event><post>{POST}</post>", story=False)

    assert (output.status, output.failed, output.body) == ("unexpected", True, POST)


def test_a_second_event_is_dropped_and_recorded():
    output = parse_draft_output(f'<event>none</event><event>S1 | "{QUOTE}"</event><post>{POST}</post>', story=True)

    assert output.status == "none" and _kinds(output) == ["event_repeated"]


# --- Fixes --------------------------------------------------------------------------------

def test_fixes_are_read_in_order_as_replacements_and_deletions():
    fixes, failures = parse_fixes('<fixes>\n<fix sentence="4">A new one. [[S1]]</fix>\n'
                                  '<fix sentence="7" delete="true"/>\n<fix sentence="9" delete="true"></fix>\n</fixes>')

    assert fixes == [Fix(4, "A new one. [[S1]]"), Fix(7, None), Fix(9, None)] and failures == []


def test_an_answer_with_no_fixes_block_gives_no_fixes():
    fixes, failures = parse_fixes('<fix sentence="4">A new one. [[S1]]</fix>')

    assert fixes == [] and [f["kind"] for f in failures] == ["fixes_tag_missing"]


def test_text_between_fixes_is_ignored_and_recorded_and_repeats_are_kept_for_the_validator():
    fixes, failures = parse_fixes('<fixes>Here you go.<fix sentence="2">A. [[V]]</fix>'
                                  '<fix sentence="2">B. [[V]]</fix> Done.</fixes>')

    assert [f.sentence for f in fixes] == [2, 2]
    assert [(f["kind"], f["text"]) for f in failures] == [("text_outside_fix", "Here you go."), ("text_outside_fix", "Done.")]
