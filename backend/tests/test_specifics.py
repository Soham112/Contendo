"""Specifics extractor and the unsupported-specifics check.

Examples are taken from real eval runs (ds-07, ds-08, pm-07) where the
humanizer or predictability audit added or changed facts.
"""

import pytest

from utils.specifics import extract_specifics, grounding_texts, unsupported_specifics


def kinds(text):
    return [(s.kind, s.value, s.unit) for s in extract_specifics(text)]


def flagged(output, *sources):
    return [s.text for s in unsupported_specifics(output, sources)]


# --- extraction --------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("runs about 34% above the weekly baseline", [("percent", 34.0, "")]),
    ("Twenty-five percent wrong", [("percent", 25.0, "")]),
    ("wrong by 18 to 26%", [("percent", 18.0, ""), ("percent", 26.0, "")]),
    ("18-26% underforecast", [("percent", 18.0, ""), ("percent", 26.0, "")]),
    ("cost ~410k SEK", [("number", 410000.0, "")]),
    ("cost 410,000 SEK", [("number", 410000.0, "")]),
    ("raised 1.6 million euros", [("number", 1600000.0, "")]),
    ("a 9-minute reactive lag", [("duration", 9.0, "minute")]),
    ("Nine minutes.", [("duration", 9.0, "minute")]),
    ("I'd spent three days writing", [("duration", 3.0, "day")]),
    ("Four winters ago", [("ago", 4.0, "winter")]),
    ("Last winter, I watched", [("time", "last winter", "")]),
    ("jumped 60% that first month", [("percent", 60.0, ""), ("time", "first month", "")]),
    ("Thursday afternoon", [("weekday", "thursday", "")]),
    ("pre-Christmas spike in December", [("month", "december", "")]),
    ("eleven pages", [("number", 11.0, "")]),
    ("our twelve-page PRDs", [("number", 12.0, "")]),
    ("in week 50 of 2024", [("number", 50.0, ""), ("number", 2024.0, "")]),
])
def test_extracts_specifics(text, expected):
    assert kinds(text) == expected


@pytest.mark.parametrize("text", [
    "one page, no one, one engineer",   # "one" is too common to be a fact
    "renamed booking_ts to booked_at",  # identifiers, not numbers
    "It may be worth it this week.",    # lowercase "may", anaphoric "this week"
    "Volume dropped that month.",
])
def test_ignores_non_specifics(text):
    assert kinds(text) == []


# --- the check: real fabrications are caught ----------------------------------

DS08_CHUNKS = [
    "Incident note. An upstream booking team at Fernhollow Logistics renamed a column from "
    "booking_ts to booked_at. For six days Kestrel saw zero recent bookings for one region.",
    "Learning notes on reconciling forecasts across a hierarchy, for example depot, region, and national totals.",
]
DS08_DRAFT = "A depot manager who orders from the booking log two days prior is never behind."


def test_ds08_humanizer_additions_are_flagged():
    output = (
        "At Fernhollow, our Thursday afternoon booking volume runs about 34% above the weekly baseline. "
        "That surge is visible roughly 18 hours before the load arrives. A 9-minute reactive lag cost us "
        "capacity while carriers confirmed Friday loads. It broke six days ago. Orders from the log two days prior."
    )
    assert flagged(output, DS08_DRAFT, *DS08_CHUNKS) == ["Thursday", "34%", "18 hours", "9-minute", "Friday"]


def test_pm07_eleven_pages_is_an_alteration_of_twelve_page():
    chunk = "Observation: our twelve-page PRDs were read by the author and one reviewer."
    output = "Eleven pages, untouched. Twelve pages gave people somewhere to hide. Review comments jumped 60% that first month."
    assert flagged(output, chunk) == ["Eleven", "60%", "first month"]


def test_ds07_changed_range_is_flagged_but_reformatted_range_is_not():
    chunk = "experienced 18-26% underforecast at northern depots pre-Christmas costing ~410k SEK."
    assert flagged("It was wrong by 18 to 26% and cost 410,000 SEK.", chunk) == []
    assert flagged("Twenty-five percent wrong in one depot. Three percent wrong everywhere.", chunk) == [
        "Twenty-five percent", "Three percent",
    ]


# --- the check: legitimate rewording passes ------------------------------------

@pytest.mark.parametrize("output, source", [
    ("cost us around 410,000 SEK", "costing ~410k SEK"),
    ("We spent nine minutes on it", "a 9-minute call"),
    ("44% active three months after launch", "44 percent opened it at 90 days"),
    ("It broke six days ago", "For six days Kestrel saw zero bookings"),
    ("We raised 1.6 million euros", "a 1.6m EUR seed round"),
    ("the 26 depots", "26% of depots"),       # bare number restating a sourced figure
    ("Eighteen hours later", "18 hours later"),
])
def test_equivalent_forms_are_supported(output, source):
    assert flagged(output, source) == []


def test_a_specific_in_a_source_but_used_with_another_unit_is_flagged():
    # "18" exists (as a percentage) but "18 hours" is a new fact.
    assert flagged("visible 18 hours before", "18-26% underforecast") == ["18 hours"]


def test_each_unsupported_specific_is_reported_once():
    assert flagged("34% here, 34% there, and 34% again", "nothing") == ["34%"]


# --- grounding sources -----------------------------------------------------------

def test_grounding_texts_include_draft_chunks_profile_topic_and_context():
    state = {
        "retrieval_bundle": {"chunks": [{"text": "chunk with 38 percent"}]},
        "retrieved_chunks": ["[source_type: note] flat chunk 61 percent"],
        "profile": {"bio": "Seven years in data", "writing_samples": ["We shipped in 4 weeks"]},
        "topic": "Why 2024 was hard",
        "context": "we cut churn 40%",
    }
    sources = grounding_texts(state, "draft says 12 clinics")
    output = "12 clinics, 38%, 61%, seven years, four weeks, 2024, and 40%."
    assert unsupported_specifics(output, sources) == []
    assert [s.text for s in unsupported_specifics("and 99%", sources)] == ["99%"]
