"""Length through run_pipeline: the single-writer variants trim an over-length
post, never lengthen one, and return no post when the draft was cut off; the
draft's output budget fits every length target; pipeline A is recorded only.
The runs here have no review (variant C, and B at quality="draft"); what
standard B does about length is in test_pipeline_b.py."""

import json

import pytest

from tests.conftest import ARCHETYPE_GENERAL, CRITIC_ALL_STRONG
from tests.generation_fixtures import OWN, enveloped, make_state
from tests.length_fixtures import DRAFT_ONLY, FIRST_POST_USER, KB_USER, _clean, _cut_off, _lines, _outputs, _post, _run
from tests.test_generation_trace import STANDARD_RUN, seeded_kb  # noqa: F401  (shared fixture)
from utils.formatters import FIRST_POST_RANGE, WORD_RANGES, count_words, resolve_length_target


# --- Through run_pipeline, draft only (C, and B at quality="draft") ---------------

@pytest.mark.parametrize("variant,quality", DRAFT_ONLY)
def test_a_first_post_made_over_length_by_normalisation_is_trimmed(claude, fake_db, variant, quality):
    # Ten 10-word lines: 100 words, the first-post maximum. One holds "alpha—beta",
    # which is one word until the em dash is normalised: then the post is 101.
    lines = _lines(10)
    lines[4] = lines[4].replace("word", "alpha—beta", 1)
    marked = "\n\n".join(lines)
    assert count_words(_clean(marked)) == FIRST_POST_RANGE[1]      # 100 before normalisation
    claude.queue(ARCHETYPE_GENERAL, enveloped(marked), json.dumps({"ranking": [2]}))

    result = _run(variant, quality=quality, user_id=FIRST_POST_USER, topic="Forecast intervals",
                  context="Core opinion/take: intervals beat point forecasts")

    outputs = _outputs(fake_db)
    assert outputs["length_target"]["basis"] == "first_post"
    assert outputs["trim_result"]["words_before"] == FIRST_POST_RANGE[1] + 1      # validated after normalisation
    assert outputs["trim_result"]["outcome"] == "trimmed"
    assert "alpha, beta" in result["post"] and "—" not in result["post"]
    assert outputs["final_validation"]["words"] == count_words(result["post"]) <= FIRST_POST_RANGE[1]
    assert outputs["final_post"] == result["post"]
    assert [c["event_type"] for c in fake_db.tables["generation_traces"][0]["llm_calls"]] == ["archetype", "generate", "trim"]


@pytest.mark.parametrize("variant,quality", DRAFT_ONLY)
def test_an_over_length_post_is_trimmed_and_the_returned_post_is_the_validated_one(claude, fake_db, seeded_kb, variant, quality):
    claude.queue(ARCHETYPE_GENERAL, enveloped(_post(36)), json.dumps({"ranking": [10]}))   # 360 words against 250-350

    result = _run(variant, quality=quality)

    outputs = _outputs(fake_db)
    assert outputs["trim_result"]["outcome"] == "trimmed"
    assert (outputs["trim_result"]["words_before"], outputs["trim_result"]["words_after"]) == (360, 350)
    assert outputs["trim_result"]["deleted"] == [{"index": 9, "span": 9, "text": _clean(_lines(36)[9])}]
    assert result["status"] == "ok"
    assert result["post"] == outputs["final_post"]
    assert outputs["final_validation"]["words"] == count_words(result["post"]) == 350
    assert [d["node"] for d in outputs["draft_history"]] == ["draft", "trim"]
    assert len(outputs["citations"]) == 35


@pytest.mark.parametrize("variant,quality", DRAFT_ONLY)
def test_a_failed_trim_returns_the_post_with_the_failure_recorded(claude, fake_db, seeded_kb, variant, quality):
    claude.queue(ARCHETYPE_GENERAL, enveloped(_post(36)), json.dumps({"ranking": [99]}))

    result = _run(variant, quality=quality)

    outputs = _outputs(fake_db)
    assert outputs["trim_result"]["outcome"] == "trim_failed"
    assert outputs["trim_result"]["reason"].startswith("invalid_indices")
    assert result["status"] == "ok" and count_words(result["post"]) == 360
    assert outputs["final_validation"]["length"] == "over_length" and outputs["final_validation"]["over_by"] == 10
    assert result["post"] == outputs["final_post"]


@pytest.mark.parametrize("variant,quality", DRAFT_ONLY)
def test_an_under_length_post_is_recorded_and_costs_no_extra_call(claude, fake_db, seeded_kb, variant, quality):
    claude.queue(ARCHETYPE_GENERAL, enveloped(_post(5)))          # 50 words against 250-350

    result = _run(variant, quality=quality)

    outputs = _outputs(fake_db)
    assert len(claude.calls) == 2                      # structure and draft: nothing lengthens a post
    assert outputs["final_validation"]["length"] == "under_length"
    assert (outputs["final_validation"]["words"], outputs["final_validation"]["under_by"]) == (50, 200)
    assert "trim_result" not in outputs
    assert result["post"] == outputs["final_post"] and count_words(result["post"]) == 50


@pytest.mark.parametrize("variant,quality", DRAFT_ONLY)
def test_a_post_within_its_target_is_not_trimmed(claude, fake_db, seeded_kb, variant, quality):
    claude.queue(ARCHETYPE_GENERAL, enveloped(_post(30)))         # 300 words

    _run(variant, quality=quality)

    assert len(claude.calls) == 2
    assert _outputs(fake_db)["final_validation"]["length"] == "ok"
    assert "trim_result" not in _outputs(fake_db)


# --- Truncated drafts ------------------------------------------------------------

@pytest.mark.parametrize("variant", ["B", "C"])
def test_a_cut_off_draft_returns_an_error_status_and_no_post(claude, fake_db, seeded_kb, variant):
    from pipeline.graph import DRAFT_TRUNCATED_MESSAGE

    cut = "pgvector makes retrieval fast. [[S1]]\n\nAnd the reason it matters is that"
    claude.queue(ARCHETYPE_GENERAL, _cut_off(cut))

    result = _run(variant)

    assert result["status"] == "draft_truncated"
    assert result["post"] == ""
    assert result["message"] == DRAFT_TRUNCATED_MESSAGE
    assert len(claude.calls) == 2                      # no trim, no second draft
    outputs = _outputs(fake_db)
    assert outputs["draft_truncated"] == {"max_tokens": 2000, "output_tokens": 2000}
    assert outputs["final_post"] == ""
    assert outputs["draft_history"] == [{"node": "draft", "iteration": 0, "text": cut}]   # kept for diagnosis only
    assert "final_validation" not in outputs


def test_the_generate_endpoint_reports_a_cut_off_draft(claude, fake_db, seeded_kb, client, auth_headers, monkeypatch):
    from pipeline.graph import DRAFT_TRUNCATED_MESSAGE

    monkeypatch.setenv("PIPELINE_VARIANT", "C")
    claude.queue(ARCHETYPE_GENERAL, _cut_off("pgvector makes retrieval"))

    resp = client.post("/generate", json={"topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"},
                       headers=auth_headers(KB_USER))

    assert resp.status_code == 200
    body = resp.json()
    assert (body["status"], body["post"], body["message"]) == ("draft_truncated", "", DRAFT_TRUNCATED_MESSAGE)


def test_an_ordinary_response_has_an_empty_message(claude, fake_db, seeded_kb, client, auth_headers):
    claude.queue(*STANDARD_RUN)

    resp = client.post("/generate", json={"topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"},
                       headers=auth_headers(KB_USER))

    assert resp.json()["status"] == "ok" and resp.json()["message"] == ""


# --- The draft's output budget ---------------------------------------------------

def _every_target():
    targets = [resolve_length_target(fmt, length) for fmt, lengths in WORD_RANGES.items() for length in lengths]
    targets += [resolve_length_target(fmt, length, thin_sources=True) for fmt, lengths in WORD_RANGES.items() for length in lengths]
    return targets + [resolve_length_target("linkedin post", "standard", first_post=True)]


def test_the_draft_budget_fits_every_length_target_with_markers():
    from llm.models import MODELS, spec
    from utils.formatters import DRAFT_TOKEN_MARGIN, MIN_DRAFT_MAX_TOKENS, TOKENS_PER_WORD, draft_max_tokens

    assert max(t["max_words"] for t in _every_target()) == 1800      # Medium long-form is in the table
    for model in MODELS:
        per_word = TOKENS_PER_WORD[spec(model).tokenizer]
        for target in _every_target():
            budget = draft_max_tokens(target, model)
            assert budget >= target["max_words"] * per_word * DRAFT_TOKEN_MARGIN, (model, target)
            assert budget >= MIN_DRAFT_MAX_TOKENS
        assert draft_max_tokens(resolve_length_target("thread", "long-form"), model) == MIN_DRAFT_MAX_TOKENS
    assert DRAFT_TOKEN_MARGIN > 1


def test_the_largest_draft_budget_is_within_the_non_streaming_ceiling():
    from llm.client import MAX_NON_STREAMING_OUTPUT_TOKENS, THINKING_ALLOWANCE_TOKENS, output_budget
    from llm.models import MODELS, spec
    from utils.formatters import draft_max_tokens

    for model in MODELS:
        # The draft and the model's thinking both fit: the ceiling never has to cut the allowance.
        largest = max(draft_max_tokens(t, model) for t in _every_target())
        room = THINKING_ALLOWANCE_TOKENS if spec(model).thinks else 0
        assert output_budget(model, largest) == largest + room <= MAX_NON_STREAMING_OUTPUT_TOKENS, model


@pytest.mark.parametrize("fmt,length,expected", [
    ("linkedin post", "standard", 2000), ("medium article", "standard", 2138), ("medium article", "long-form", 4275),
])
def test_the_draft_call_asks_for_the_budget_its_target_needs(claude, fmt, length, expected):
    from agents.draft_agent import cited_draft_node

    claude.queue("The post. [[V]]")
    cited_draft_node(make_state([OWN], archetype="general", format=fmt, length=length,
                                length_target=resolve_length_target(fmt, length)))

    assert claude.calls[0]["max_tokens"] == expected


# --- Pipeline A: recorded only ----------------------------------------------------

def test_pipeline_a_returns_the_same_post_and_stores_the_validation_record(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)

    result = _run("A")

    record = _outputs(fake_db)["final_validation"]
    assert result["post"] == "Final text."               # what STANDARD_RUN has always produced
    assert record["words"] == count_words(result["post"]) == 2
    assert (record["length"], record["under_by"]) == ("under_length", 248)
    assert record["target"] == {"min_words": 250, "max_words": 350, "basis": "length_setting"}
    assert "trim_result" not in _outputs(fake_db)


def test_pipeline_a_first_post_made_101_words_by_normalisation_is_recorded_and_returned_unchanged(claude, fake_db):
    from utils.formatters import normalise_post_punctuation

    draft = " ".join(["word"] * 99) + " alpha—beta"     # 100 words to the enforcer, 101 once normalised
    claude.queue(ARCHETYPE_GENERAL, draft, CRITIC_ALL_STRONG, draft, "CLEAN", draft)

    result = _run("A", user_id=FIRST_POST_USER, topic="Forecast intervals",
                  context="Core opinion/take: intervals beat point forecasts")

    [trace] = fake_db.tables["generation_traces"]
    record = trace["node_outputs"]["final_validation"]
    assert result["post"] == normalise_post_punctuation(draft)       # exactly what A returned before this branch
    assert count_words(result["post"]) == 101
    assert (record["words"], record["length"], record["over_by"]) == (101, "over_length", 1)
    assert "word_count_enforcer" not in [c["event_type"] for c in trace["llm_calls"]]   # A did not act on it
    assert len(claude.calls) == 6
