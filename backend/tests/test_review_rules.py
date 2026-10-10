"""The review's verdicts are decided in code (pipeline/review_rules.py) from the
model's observations, the sentence's own citation (which the model never sees)
and the source index. Each rule has a record that gives the issue and one that
does not. Records here are as review_agent passes them on: a detail_change or
an unsupported_part is present only if it passed its checks."""

import pytest

from tests.review_fixtures import record
from utils.citations import Span

# S1 is the author's own; S2 and S3 are external.
INDEX = {"S1": {"position": 0, "chunk_id": None, "frame": "PERSONAL_WORK", "authorship": "self"},
         "S2": {"position": 1, "chunk_id": None, "frame": "LEARNING_MID", "authorship": "external"},
         "S3": {"position": 2, "chunk_id": None, "frame": "EXPERT_OUTSIDER", "authorship": "external"}}
FACT = dict(content="fact_or_event", stated_as="fact", presented_as="neutral")


def _sentence(citation="S1", text="A sentence of the post.") -> Span:
    if citation in ("view", "uncited", "request"):
        return Span(0, len(text), text, citation, ())
    return Span(0, len(text), text, "sources", tuple(citation.split(",")))


def _types(citation="S1", **changes) -> list[str]:
    from pipeline.review_rules import derive_issues

    return [i["type"] for i in derive_issues([record(1, **changes)], [(0, _sentence(citation))], INDEX)]


def test_a_benign_record_gives_no_issue_and_there_are_seven_types():
    from pipeline.review_rules import ISSUE_TYPES

    assert _types("view") == []
    assert ISSUE_TYPES == ("not_in_sources", "changed_detail", "wrong_citation", "wrong_attribution",
                           "cross_source_link", "off_topic", "ai_rhythm")


# --- not_in_sources ---------------------------------------------------------------

@pytest.mark.parametrize("content,stated_as", [
    ("fact_or_event", "fact"), ("fact_or_event", "authors_view"), ("feeling_or_reaction", "fact"),
    ("motive", "fact"), ("generalisation", "fact"),
])
def test_content_that_needs_a_source_and_has_none_is_not_in_sources(content, stated_as):
    for citation in ("S1", "view", "uncited"):
        assert _types(citation, content=content, stated_as=stated_as, presented_as="neutral") == ["not_in_sources"]


@pytest.mark.parametrize("changes", [
    dict(content="generalisation", stated_as="authors_view", presented_as="authors_view"),   # framed as the author's view
    dict(content="opinion"), dict(content="advice_or_question"), dict(content="disclaimer", stated_as="fact"),
    dict(content="analogy_or_comparison"), dict(content="analogy_or_comparison", presented_as="neutral"),
    dict(content="other", stated_as="fact", presented_as="neutral"),
])
def test_content_that_is_the_authors_own_needs_no_source(changes):
    assert _types("view", **changes) == []


def test_a_supported_fact_is_not_not_in_sources():
    assert _types("S1", **FACT, supported_by=["S1"]) == []
    assert _types("request", **FACT, supported_by=["request"]) == []


def test_an_analogy_told_as_something_that_happened_needs_a_source():
    assert _types("view", content="analogy_or_comparison", stated_as="fact",
                  presented_as="author_did_or_experienced") == ["not_in_sources"]


# --- wrong_citation ---------------------------------------------------------------

@pytest.mark.parametrize("citation,supported_by", [
    ("view", ["S1"]), ("uncited", ["S1"]), ("S2", ["S1"]), ("S1,S2", ["S1"]),
    ("request", ["S1"]), ("S1", ["request"]), ("view", ["request"]),
])
def test_a_supported_sentence_whose_citation_points_elsewhere_is_a_wrong_citation(citation, supported_by):
    from pipeline.review_rules import derive_issues

    [issue] = derive_issues([record(1, **FACT, supported_by=supported_by)], [(0, _sentence(citation))], INDEX)

    assert issue["type"] == "wrong_citation"
    assert issue["sources"] == [sid for sid in supported_by if sid != "request"]
    assert issue["detail"]["supported_by"] == supported_by


@pytest.mark.parametrize("citation,supported_by", [
    ("S1", ["S1"]), ("S1", ["S1", "S2"]), ("S1,S2", ["S2", "S1"]), ("request", ["request"]), ("request", ["S1", "request"]),
])
def test_a_citation_that_names_only_places_that_state_it_is_right(citation, supported_by):
    assert _types(citation, **FACT, supported_by=supported_by) == []


@pytest.mark.parametrize("content", ["opinion", "advice_or_question", "disclaimer", "analogy_or_comparison"])
def test_the_authors_own_content_is_never_a_wrong_citation_even_when_a_source_echoes_it(content):
    assert _types("view", content=content, supported_by=["S1"]) == []


def test_wrong_citation_is_decided_by_the_citation_alone():
    # Identical records; only the sentence's citation differs.
    observed = dict(**FACT, supported_by=["S1"], evidence="x")

    assert _types("S1", **observed) == []
    assert _types("view", **observed) == ["wrong_citation"]
    assert _types("S2", **observed) == ["wrong_citation"]


# --- not_in_sources from an unsupported part --------------------------------------

def test_words_nothing_states_in_a_sentence_stated_as_fact_are_not_in_sources():
    from pipeline.review_rules import derive_issues

    [issue] = derive_issues([record(1, **FACT, supported_by=["S1"], unsupported_part="trying to find the fix")],
                            [(0, _sentence("S1"))], INDEX)

    assert issue["type"] == "not_in_sources"
    assert issue["detail"]["unsupported_part"] == "trying to find the fix"


@pytest.mark.parametrize("changes", [
    dict(**FACT, supported_by=["S1"]),                                                  # nothing unsupported
    dict(content="generalisation", stated_as="authors_view", presented_as="authors_view",
         unsupported_part="most teams"),                                                # stated as the author's view
    dict(content="disclaimer", stated_as="fact", presented_as="neutral", supported_by=["S1"],
         unsupported_part="not something we implemented"),                              # a disclaimer is the author's own
    dict(content="opinion", stated_as="fact", unsupported_part="a fair trade"),
])
def test_an_unsupported_part_gives_no_issue_when_it_is_the_authors_own_or_absent(changes):
    assert "not_in_sources" not in _types("S1", **changes)


def test_a_wholly_unsupported_sentence_with_an_unsupported_part_is_one_issue_not_two():
    assert _types("S1", **FACT, unsupported_part="all of it") == ["not_in_sources"]


# --- changed_detail ---------------------------------------------------------------

def test_a_detail_change_is_a_changed_detail_quoting_both_sides():
    from pipeline.review_rules import derive_issues

    [issue] = derive_issues([record(1, **FACT, supported_by=["S1"], evidence="Early meetings were me presenting",
                                    detail_change={"source_words": "Early meetings", "post_words": "first board meetings"})],
                            [(0, _sentence("S1"))], INDEX)

    assert (issue["type"], issue["sources"], issue["evidence"]) == ("changed_detail", ["S1"], "Early meetings")
    assert issue["detail"] == {"source_words": "Early meetings", "post_words": "first board meetings"}


def test_no_changed_detail_without_a_detail_change():
    assert _types("S1", **FACT, supported_by=["S1"], evidence="x") == []
    assert _types("S1", **FACT, supported_by=["S1"], evidence="x", detail_change=None) == []


# --- wrong_attribution ------------------------------------------------------------

@pytest.mark.parametrize("presented_as,supported_by,citation,expected", [
    ("author_did_or_experienced", ["S2"], "S2", ["wrong_attribution"]),            # external, told as the author's own
    ("author_did_or_experienced", ["S2", "S3"], "S2", ["wrong_attribution"]),
    ("author_did_or_experienced", ["S1"], "S1", []),                               # the author's own note
    ("author_did_or_experienced", ["S1", "S2"], "S1", []),                         # not every supporter is external
    ("a_source_says", ["S1"], "S1", ["wrong_attribution"]),                        # the author's own, credited to a source
    ("a_source_says", ["S2"], "S2", []),
    ("a_source_says", ["S1", "S2"], "S2", []),
    ("neutral", ["S2"], "S2", []),
    ("authors_view", ["S2"], "S2", []),
])
def test_wrong_attribution_follows_how_it_is_presented_and_whose_the_supporting_sources_are(presented_as, supported_by,
                                                                                         citation, expected):
    assert _types(citation, content="fact_or_event", stated_as="fact", presented_as=presented_as,
                  supported_by=supported_by) == expected


def test_wrong_attribution_is_decided_by_the_source_index_alone():
    from pipeline.review_rules import derive_issues

    observed = record(1, content="fact_or_event", stated_as="fact", presented_as="author_did_or_experienced", supported_by=["S1"])
    as_own = {"S1": {**INDEX["S1"], "authorship": "self"}}
    as_external = {"S1": {**INDEX["S1"], "authorship": "external"}}

    assert derive_issues([observed], [(0, _sentence("S1"))], as_own) == []
    assert [i["type"] for i in derive_issues([observed], [(0, _sentence("S1"))], as_external)] == ["wrong_attribution"]


def test_something_credited_to_a_source_that_no_source_states_is_a_wrong_attribution():
    assert _types("S2", content="opinion", stated_as="fact", presented_as="a_source_says") == []      # the author's own content
    assert _types("S2", content="fact_or_event", stated_as="fact", presented_as="a_source_says") == [
        "not_in_sources", "wrong_attribution"]
    assert _types("view", content="analogy_or_comparison", stated_as="fact", presented_as="a_source_says") == ["wrong_attribution"]


@pytest.mark.parametrize("content", ["disclaimer", "opinion", "advice_or_question"])
def test_a_disclaimer_or_the_authors_own_view_is_never_a_wrong_attribution(content):
    # "Not something we implemented", about an external source, in the first person.
    assert _types("S2", content=content, stated_as="fact", presented_as="author_did_or_experienced", supported_by=["S2"]) == []


def test_an_analogy_offered_as_the_authors_own_framing_gives_no_issue():
    for presented_as in ("authors_view", "neutral"):
        assert _types("view", content="analogy_or_comparison", stated_as="authors_view", presented_as=presented_as) == []
        assert _types("view", content="analogy_or_comparison", stated_as="authors_view", presented_as=presented_as,
                      supported_by=["S2"]) == []


# --- cross_source_link ------------------------------------------------------------

def test_facts_from_two_sources_linked_with_no_source_stating_the_link_is_a_cross_source_link():
    from pipeline.review_rules import derive_issues

    [issue] = derive_issues([record(1, **FACT, supported_by=["S1", "S2"], link={"sources": ["S2", "S1", "S2"]})],
                            [(0, _sentence("S1,S2"))], INDEX)

    assert (issue["type"], issue["sources"]) == ("cross_source_link", ["S1", "S2"])


@pytest.mark.parametrize("changes", [
    dict(),                                                                         # no link at all
    dict(link=None),
    dict(link={"sources": ["S1"]}),                                                 # one source
    dict(link={"sources": ["S1", "S1"]}),
    dict(link={"sources": ["S1", "S2"], "stated_by": ["S2"]}),                      # a source states the link
    dict(link={"sources": []}),
])
def test_no_cross_source_link_without_a_link_across_sources_that_nothing_states(changes):
    assert _types("S1,S2", **FACT, supported_by=["S1", "S2"], **changes) == []


# --- off_topic --------------------------------------------------------------------

def test_off_topic_follows_the_flag():
    assert _types("view", off_topic=True) == ["off_topic"]
    assert _types("view", off_topic=False) == []


# --- Several at once, and positions --------------------------------------------------

def test_a_sentence_can_give_more_than_one_issue_and_issues_say_where_they_are():
    from pipeline.review_rules import derive_issues

    records = [record(1), record(2, content="fact_or_event", stated_as="fact", presented_as="author_did_or_experienced",
                                 supported_by=["S2"], evidence="x", off_topic=True,
                                 detail_change={"source_words": "nine", "post_words": "eight"})]
    sentences = [(0, _sentence("view", "First.")), (4, _sentence("view", "Second."))]

    issues = derive_issues(records, sentences, INDEX)

    assert [i["type"] for i in issues] == ["wrong_citation", "changed_detail", "wrong_attribution", "off_topic"]
    assert {(i["sentence"], i["span"], i["text"]) for i in issues} == {(1, 4, "Second.")}


def test_records_with_only_the_four_required_fields_are_enough():
    from pipeline.review_rules import derive_issues

    bare = {"sentence": 1, "content": "fact_or_event", "stated_as": "fact", "presented_as": "neutral"}

    assert [i["type"] for i in derive_issues([bare], [(0, _sentence("S1"))], INDEX)] == ["not_in_sources"]
    assert derive_issues([{**bare, "content": "opinion"}], [(0, _sentence("view"))], INDEX) == []
