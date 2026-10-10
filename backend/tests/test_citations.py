"""Citation markers (utils/citations.py): the grammar, stripping a marked draft
into clean text and spans, and reporting marker-like text that is not a citation."""

import pytest

from utils.citations import escape_markers, leftover_markers, source_id, strip_citations


def _spans(text):
    return [(s.text, s.basis, s.sources) for s in strip_citations(text).spans]


def _failures(text):
    return [(f.kind, f.text) for f in strip_citations(text).failures]


# --- Grammar ------------------------------------------------------------------

@pytest.mark.parametrize("marker,basis,sources", [
    ("[[S1]]", "sources", ("S1",)),
    ("[[S12]]", "sources", ("S12",)),
    ("[[S1,S3]]", "sources", ("S1", "S3")),
    ("[[S1, S3]]", "sources", ("S1", "S3")),
    ("[[ S2 , S10 ]]", "sources", ("S2", "S10")),
    ("[[S3,S1]]", "sources", ("S3", "S1")),
    ("[[S1,S1]]", "sources", ("S1",)),
    ("[[R]]", "request", ()),
    ("[[V]]", "view", ()),
])
def test_valid_markers(marker, basis, sources):
    result = strip_citations(f"Latency fell after the rebuild. {marker}")

    assert result.text == "Latency fell after the rebuild."
    assert _spans(f"Latency fell after the rebuild. {marker}") == [("Latency fell after the rebuild.", basis, sources)]
    assert result.failures == ()


@pytest.mark.parametrize("marker", [
    "[[S0]]", "[[S01]]", "[[s1]]", "[[S]]", "[[1]]", "[[S1,]]", "[[,S1]]", "[[S1;S2]]", "[[S1 S2]]",
    "[[S1,R]]", "[[R,V]]", "[[RV]]", "[[r]]", "[[v]]", "[[]]", "[[ ]]", "[[S1.5]]", "[[source 1]]",
    "[[opinion]]", "[[S-1]]",
])
def test_malformed_markers_are_reported_removed_and_cite_nothing(marker):
    result = strip_citations(f"Latency fell after the rebuild. {marker}")

    assert [(f.kind, f.text) for f in result.failures] == [("malformed", marker)]
    assert result.text == "Latency fell after the rebuild."
    assert [(s.text, s.basis) for s in result.spans] == [("Latency fell after the rebuild.", "uncited")]


@pytest.mark.parametrize("text,kind,found", [
    ("Latency fell. [S1]", "single_brackets", "[S1]"),
    ("Latency fell. [S1, S2]", "single_brackets", "[S1, S2]"),
    ("Latency fell. [V]", "single_brackets", "[V]"),
    ("Latency fell. [R]", "single_brackets", "[R]"),
    ("Latency fell. [[S1]", "unbalanced", "[["),
    ("Latency fell. S1]]", "unbalanced", "]]"),
    ("Latency fell. [[S1\n]]", "unbalanced", "[["),
])
def test_marker_like_text_that_is_not_a_marker_is_reported_and_left_in_place(text, kind, found):
    result = strip_citations(text)

    assert (kind, found) in [(f.kind, f.text) for f in result.failures]
    assert found in result.text
    assert all(s.basis == "uncited" for s in result.spans)


def test_ordinary_brackets_are_not_markers():
    text = "See [the docs](https://example.com/a) and the list [1], [a] and [DIAGRAM: one box]. [[V]]"

    result = strip_citations(text)

    assert result.failures == ()
    assert result.text == text.removesuffix(" [[V]]")


def test_failure_offsets_point_into_the_marked_text():
    text = "One. [[S1]] Two. [[nope]] Three. [S2]"

    for failure in strip_citations(text).failures:
        assert text[failure.start:failure.end] == failure.text


def test_source_ids_count_from_one():
    assert [source_id(i) for i in range(3)] == ["S1", "S2", "S3"]


# --- Spans --------------------------------------------------------------------

def test_a_span_is_the_text_between_markers_on_a_line():
    text = ("Nobody opened the dashboard. [[S2]]\n"
            "\n"
            "We rebuilt the ranker in March. [[S1]] Latency fell and it held. [[S1,S3]] That is the whole trick. [[V]]\n"
            "You asked about pricing. [[R]]")

    result = strip_citations(text)

    assert result.text == ("Nobody opened the dashboard.\n"
                           "\n"
                           "We rebuilt the ranker in March. Latency fell and it held. That is the whole trick.\n"
                           "You asked about pricing.")
    assert _spans(text) == [
        ("Nobody opened the dashboard.", "sources", ("S2",)),
        ("We rebuilt the ranker in March.", "sources", ("S1",)),
        ("Latency fell and it held.", "sources", ("S1", "S3")),
        ("That is the whole trick.", "view", ()),
        ("You asked about pricing.", "request", ()),
    ]
    assert result.failures == ()


def test_span_offsets_point_into_the_clean_text():
    result = strip_citations("  One thing. [[S1]]   Another thing. [[V]]\n\nA third.[[R]]\nNo marker.")

    assert len(result.spans) == 4
    for span in result.spans:
        assert result.text[span.start:span.end] == span.text
        assert span.text == span.text.strip()


def test_punctuation_after_a_marker_stays_with_its_span():
    text = 'Latency fell 40% [[S1]]. She said "it held [[S2]]." Then what [[V]]?'

    assert strip_citations(text).text == 'Latency fell 40%. She said "it held." Then what?'
    assert _spans(text) == [
        ("Latency fell 40%.", "sources", ("S1",)),
        ('She said "it held."', "sources", ("S2",)),
        ("Then what?", "view", ()),
    ]


def test_a_marker_does_not_reach_back_across_a_line_break():
    text = "The hook has no marker.\n\nThe second line has one. [[S1]]"

    assert _spans(text) == [
        ("The hook has no marker.", "uncited", ()),
        ("The second line has one.", "sources", ("S1",)),
    ]


def test_text_after_the_last_marker_on_a_line_is_uncited():
    assert _spans("Cited. [[S1]] Trailing claim with no marker.") == [
        ("Cited.", "sources", ("S1",)),
        ("Trailing claim with no marker.", "uncited", ()),
    ]


@pytest.mark.parametrize("text", [
    "[[V]]",
    "A real span. [[S1]]\n\n[[V]]",
    "A real span. [[S1]]\n[[V]]\n",
    "A real span. [[S1]] [[V]]",
    "A real span. [[S1]]\n[[S2]]\nAnother. [[V]]",
    "... [[S1]]",
])
def test_a_marker_with_no_prose_before_it_is_an_empty_span(text):
    result = strip_citations(text)

    assert [f.kind for f in result.failures] == ["empty_span"]
    assert "[[" not in result.text
    assert all(s.basis != "uncited" for s in result.spans)


def test_headings_and_placeholder_lines_need_no_marker():
    text = ("## Why it broke\n"
            "The schema changed upstream. [[S1]]\n"
            "[DIAGRAM: flow from source table to feature store]\n"
            "[IMAGE: screenshot of the alert]\n"
            "---\n"
            "### What we changed [[V]]")

    assert _spans(text) == [
        ("The schema changed upstream.", "sources", ("S1",)),
        ("### What we changed", "view", ()),
    ]
    assert strip_citations(text).failures == ()


def test_thread_numbering_is_part_of_its_span():
    assert _spans("1/ Intervals beat point forecasts. [[S2]]\n2/ Here is why. [[V]]") == [
        ("1/ Intervals beat point forecasts.", "sources", ("S2",)),
        ("2/ Here is why.", "view", ()),
    ]


def test_an_empty_draft_has_no_spans_and_no_failures():
    for text in ("", "\n\n", "   "):
        result = strip_citations(text)
        assert (result.text, result.spans, result.failures) == (text, (), ())


# --- Code and other protected text ------------------------------------------------

def test_markers_inside_code_are_left_exactly_as_written():
    text = ("In R you index a list like this. [[S1]]\n"
            "\n"
            "```r\n"
            "first <- results[[1]]\n"
            "cite <- \"[[S2]]\"\n"
            "```\n"
            "\n"
            "Inline it is `x[[S3]]` and that is fine. [[V]]")

    result = strip_citations(text)

    assert "first <- results[[1]]\ncite <- \"[[S2]]\"" in result.text
    assert "`x[[S3]]`" in result.text
    assert result.failures == ()
    assert _spans(text) == [
        ("In R you index a list like this.", "sources", ("S1",)),
        ("Inline it is `x[[S3]]` and that is fine.", "view", ()),
    ]


def test_code_lines_are_not_uncited_spans():
    text = "```python\nprint('no marker needed here')\n```\n\n    indented = code\n"

    assert strip_citations(text).spans == ()


def test_a_marker_inside_a_url_is_untouched():
    text = "The write-up is at https://example.com/a[[S1]]b and worth reading. [[S2]]"

    result = strip_citations(text)

    assert "https://example.com/a[[S1]]b" in result.text
    assert _spans(text) == [("The write-up is at https://example.com/a[[S1]]b and worth reading.", "sources", ("S2",))]


def test_a_marker_inside_quotation_marks_is_still_a_marker():
    assert _spans('She called it "the quiet failure [[S1]]" and moved on. [[V]]') == [
        ('She called it "the quiet failure"', "sources", ("S1",)),
        ("and moved on.", "view", ()),
    ]


# --- Leftover markers ---------------------------------------------------------------

def test_a_clean_post_has_no_leftover_markers():
    clean = strip_citations("We rebuilt the ranker. [[S1]]\n\n```r\nx[[1]]\n```\nIt held. [[V]]").text

    assert leftover_markers(clean) == []


@pytest.mark.parametrize("text,kind", [
    ("We rebuilt the ranker. [[S1]]", "leftover"),
    ("We rebuilt the ranker. [[V]]", "leftover"),
    ("We rebuilt the ranker. [[S1 and S2]]", "malformed"),
    ("We rebuilt the ranker. [S1]", "single_brackets"),
    ("We rebuilt the ranker. [[", "unbalanced"),
])
def test_marker_like_text_in_a_final_post_is_reported(text, kind):
    [found] = leftover_markers(text)

    assert found.kind == kind
    assert text[found.start:found.end] == found.text


def test_leftover_markers_in_code_are_found_only_when_asked():
    text = "```r\nx[[S1]]\n```"

    assert leftover_markers(text) == []
    assert [f.text for f in leftover_markers(text, include_protected=True)] == ["[[S1]]"]


# --- Escaping source text ---------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "[[S9]]", "see [[S1,S2]] here", "[[V]] and [[R]]", "[S1]", "[V]", "[[", "]]", "[[S1]", "[S1]]",
    "[[[S1]]]", "[[[[S1]]]]", "`code [[S1]]`", "```\n[[S1]]\n```", "[[Obsidian note link]]", "x[[1]][[2]]",
    "[ [S1] ]", "[[S1]\n]", "[[S1]](https://example.com)", "[S1]: https://example.com", "[[\n[[S2]]\n]]",
])
def test_escaped_source_text_contains_nothing_marker_like(text):
    escaped = escape_markers(text)

    assert leftover_markers(escaped, include_protected=True) == []
    assert strip_citations(escaped).text == escaped
    assert all(s.basis == "uncited" for s in strip_citations(escaped).spans)


def test_escaping_leaves_ordinary_text_and_brackets_alone():
    text = "Notes [draft 2] on pricing: see [the deck](https://example.com), items [1] and [a]."

    assert escape_markers(text) == text


# --- The EVENT line -------------------------------------------------------------------

from utils.citations import parse_event_header  # noqa: E402


@pytest.mark.parametrize("draft,source,quote,body", [
    ('EVENT: S3 | "We cut the form to four steps."\n\nThe post. [[S3]]', "S3", "We cut the form to four steps.", "The post. [[S3]]"),
    ('EVENT: S12 | "We cut the form."\nThe post. [[V]]', "S12", "We cut the form.", "The post. [[V]]"),
    ('\n\n  EVENT: S1 |"We cut the form."  \n\n\nThe post.', "S1", "We cut the form.", "The post."),
    ('EVENT: S1 | “We cut the form.”\n\nThe post.', "S1", "We cut the form.", "The post."),
    ('EVENT: S1 | "She said "ship it" and we did."\n\nThe post.', "S1", 'She said "ship it" and we did.', "The post."),
    ('EVENT: S2 | "Result: completion went from 38 to 61 percent."\r\n\r\nThe post.', "S2",
     "Result: completion went from 38 to 61 percent.", "The post."),
])
def test_an_event_line_gives_the_source_and_the_quote_and_leaves_the_post(draft, source, quote, body):
    header = parse_event_header(draft, required=True)

    assert (header.status, header.source, header.quote) == ("cited", source, quote)
    assert header.body == body
    assert not header.failed


def test_event_none_is_an_answer_not_a_failure():
    header = parse_event_header("EVENT: none\n\nThe post. [[V]]", required=True)

    assert (header.status, header.source, header.quote, header.body) == ("none", None, None, "The post. [[V]]")
    assert not header.failed


@pytest.mark.parametrize("line", [
    "EVENT:", "EVENT: ", "EVENT: S3", 'EVENT: S3 "no pipe"', "EVENT: S3 | no quotes", 'EVENT: S3 | ""',
    'EVENT: S3 | "  "', 'EVENT: s3 | "lower case id"', 'EVENT: S0 | "no such id form"', 'EVENT: 3 | "bare number"',
    'EVENT: S1,S2 | "two sources"', "EVENT: None", "EVENT: no", 'EVENT: none | "extra"',
    'EVENT: S3 | "quote" and then more',
])
def test_a_malformed_event_line_is_a_failure_and_is_still_removed(line):
    header = parse_event_header(f"{line}\n\nThe post. [[V]]", required=True)

    assert header.status == "malformed" and header.failed
    assert (header.source, header.quote) == (None, None)
    assert header.line == line.strip()
    assert header.body == "The post. [[V]]"


@pytest.mark.parametrize("draft", [
    "The post starts straight away. [[V]]",
    "Here is the post:\n\nEVENT: S1 | \"not the first line\"\n\nThe post.",
    "event: S1 | \"wrong case\"\n\nThe post.",
    "",
])
def test_a_story_post_without_an_event_line_is_a_failure_and_the_text_is_untouched(draft):
    header = parse_event_header(draft, required=True)

    assert header.status == "missing" and header.failed
    assert header.body == draft and header.line == ""


def test_a_post_type_that_takes_no_event_line_needs_none():
    header = parse_event_header("The post. [[V]]", required=False)

    assert header.status == "absent" and not header.failed
    assert header.body == "The post. [[V]]"


@pytest.mark.parametrize("line", ['EVENT: S1 | "We cut the form."', "EVENT: none", "EVENT: nonsense"])
def test_an_event_line_on_a_post_type_that_takes_none_is_a_failure_and_is_removed(line):
    header = parse_event_header(f"{line}\n\nThe post. [[V]]", required=False)

    assert header.status == "unexpected" and header.failed
    assert header.body == "The post. [[V]]"


def test_the_event_line_never_stays_in_the_post_whatever_its_status():
    for draft, required in [('EVENT: S1 | "x y z."\n\nPost.', True), ("EVENT: none\n\nPost.", True),
                            ("EVENT: garbage\n\nPost.", True), ("EVENT: none\n\nPost.", False)]:
        assert "EVENT" not in parse_event_header(draft, required=required).body
