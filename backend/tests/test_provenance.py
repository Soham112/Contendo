"""Provenance classifier (step 3.3): paragraph offsets, the structured call, and
the confidence rule. The model's answers are queued; nothing here judges how
well it labels real text (that is the quality_v1 measurement)."""

import json

import pytest

from agents.provenance_agent import CLASSIFIER, author_context, classify_provenance
from agents.provenance_prompt import AuthorContext, SourceFacts
from llm.client import HAIKU
from utils.provenance_spans import (MAX_PARAGRAPH_CHARS, MAX_PART_CHARS, Paragraph, merge_runs,
                                    paragraphs, parts)

USER = "user-p"
AUTHOR = AuthorContext(name="Maya Rao", role="Founder", experience="WORK EXPERIENCE:\n  - Founder at Quillmark")
NOTE_FACTS = SourceFacts(title="Friday reviews", title_origin="provided", input_type="note", source_type="personal_note")
VIDEO_FACTS = SourceFacts(title="Scaling support", title_origin="provided", input_type="youtube",
                          source_type="youtube", provider_author="Some Channel")

NOTE = ("I took 200 real tickets from our design partner and compared replies by hand.\n\n"
        "It took me six hours a week, every Friday.")


def reading(authorship="user_authored", other=(), quotes=(), facts=(), uncertain=False, signed_by=None) -> str:
    return json.dumps({"reasoning": "who speaks", "signed_by": signed_by, "authorship": authorship,
                       "other_paragraphs": list(other), "evidence_quotes": list(quotes),
                       "source_facts_used": list(facts), "uncertain": uncertain})


def classify(text=NOTE, facts=NOTE_FACTS):
    return classify_provenance(text, facts=facts, author=AUTHOR, user_id=USER)


def texts(text: str, paras: list[Paragraph]) -> list[str]:
    return [text[p.start:p.end] for p in paras]


# --- Paragraphs and offsets ----------------------------------------------------------------------

def test_paragraphs_split_on_blank_lines_and_keep_offsets_into_the_text():
    text = "  First line.\nsame paragraph.\n\n \n\nSecond.\n\t\nThird  \n"
    paras = paragraphs(text)
    assert texts(text, paras) == ["First line.\nsame paragraph.", "Second.", "Third"]
    assert [p.id for p in paras] == [1, 2, 3]


def test_empty_or_blank_text_has_no_paragraphs():
    assert paragraphs("") == [] and paragraphs(" \n\n\t ") == []


def test_long_paragraph_is_cut_at_sentence_ends_within_the_limit():
    sentence = "This is one sentence of a transcript without breaks. "
    text = sentence * (3 * MAX_PARAGRAPH_CHARS // len(sentence))
    paras = paragraphs(text)
    assert len(paras) >= 3
    assert all(p.end - p.start <= MAX_PARAGRAPH_CHARS for p in paras)
    assert all(t.endswith("breaks.") for t in texts(text, paras))
    assert " ".join(texts(text, paras)) == text.strip()   # nothing lost or repeated


def test_long_paragraph_without_sentence_ends_is_cut_at_the_limit():
    text = "x" * (MAX_PARAGRAPH_CHARS * 2 + 10)
    paras = paragraphs(text)
    assert [p.end - p.start for p in paras] == [MAX_PARAGRAPH_CHARS, MAX_PARAGRAPH_CHARS, 10]


def test_parts_keep_order_and_stay_within_the_part_limit():
    block = "y" * (MAX_PARAGRAPH_CHARS - 10)
    text = "\n\n".join([block] * (2 * MAX_PART_CHARS // MAX_PARAGRAPH_CHARS + 3))
    groups = parts(paragraphs(text))
    assert len(groups) >= 3
    assert [p.id for g in groups for p in g] == [p.id for p in paragraphs(text)]
    assert all(g[-1].end - g[0].start <= MAX_PART_CHARS for g in groups)


def test_merge_runs_joins_neighbours_with_one_label_and_breaks_at_gaps():
    paras = [Paragraph(1, 0, 5), Paragraph(2, 7, 12), Paragraph(3, 14, 20), Paragraph(4, 22, 30)]
    spans = merge_runs(paras, {1: "external", 2: "external", 4: "external"})
    assert spans == [{"start": 0, "end": 12, "authorship": "external"},
                     {"start": 22, "end": 30, "authorship": "external"}]


# --- The call ------------------------------------------------------------------------------------

def test_one_haiku_call_with_numbered_paragraphs_source_facts_and_the_user(claude):
    claude.queue(*[reading(quotes=["It took me six hours a week"])] * 2)
    classify()
    assert len(claude.calls) == 2   # two samples
    call = claude.calls[0]
    assert call["model"] == HAIKU
    prompt = call["messages"][-1]["content"]
    assert "[P1] I took 200 real tickets" in prompt and "[P2] It took me six hours" in prompt
    assert "Maya Rao" in prompt and "Founder at Quillmark" in prompt
    assert "input_type: note" in prompt and "a real title" in prompt
    assert "parts" not in prompt   # one part: no part instructions


def test_confident_own_note(claude):
    claude.queue(*[reading(quotes=["It took me six hours a week"])] * 2)
    result = classify()
    assert result.authorship == "user_authored" and result.confident and result.spans == [] and result.reasons == []


def test_confident_external_from_a_given_source_fact(claude):
    claude.queue(*[reading("external", facts=["provider_author"])] * 2)
    result = classify(facts=VIDEO_FACTS)
    assert result.authorship == "external" and result.confident


def test_quotes_match_across_curly_quotes_and_whitespace(claude):
    text = "We said \"ship it\" and it's\nbeen fine."
    claude.queue(*[reading(quotes=["“ship it” and it’s been fine"])] * 2)
    assert classify(text).confident


@pytest.mark.parametrize("answer, reason", [
    (reading(uncertain=True, quotes=["It took me six hours a week"]), "uncertain"),
    (reading(quotes=["I spent ten hours a week"]), "not in the text"),
    (reading(), "no evidence"),
    (reading(other=[7], quotes=["It took me six hours a week"]), "outside this part"),
])
def test_not_confident_when_a_structural_check_fails(claude, answer, reason):
    claude.queue(answer, answer)
    result = classify()
    assert result is not None and not result.confident
    assert any(reason in r for r in result.reasons)


def test_mixed_source_stores_the_other_paragraphs_as_offsets(claude):
    text = ("Clear argues that habits compound through small daily gains.\n\n"
            "When I tried a two-minute rule at Quillmark, our standups went from forty minutes to twelve, and the "
            "team kept the habit for the whole quarter without anyone asking.\n\n"
            "The book also says identity drives behaviour.")
    claude.queue(*[reading("external", other=[2], quotes=["Clear argues"])] * 2)
    result = classify(text)
    assert result.authorship == "user_authored"   # paragraph 2 is most of the text
    passages = [text[s["start"]:s["end"]] for s in result.spans]
    assert passages == ["Clear argues that habits compound through small daily gains.",
                      "The book also says identity drives behaviour."]
    assert {s["authorship"] for s in result.spans} == {"external"}


def test_equal_sizes_resolve_to_external(claude):
    text = "abcd\n\nwxyz"
    claude.queue(*[reading("user_authored", other=[2], quotes=["abcd"])] * 2)
    result = classify(text)
    assert result.authorship == "external"
    assert result.spans == [{"start": 0, "end": 4, "authorship": "user_authored"}]


def test_the_schema_offers_only_the_facts_that_were_given(claude):
    from agents.provenance_agent import reading_schema

    def offered(facts):
        prop = reading_schema(facts).model_json_schema()["properties"]["source_facts_used"]
        return prop["items"].get("enum") if prop.get("items") else prop
    assert offered(NOTE_FACTS) == ["title", "input_type", "source_type"]
    assert offered(VIDEO_FACTS) == ["title", "input_type", "source_type", "provider_author"]
    assert reading_schema(SourceFacts()).model_json_schema()["properties"]["source_facts_used"]["maxItems"] == 0
    claude.queue(*[reading(quotes=["It took me six hours a week"])] * 2)
    classify()
    sent = claude.calls[0]["tools"][0]["input_schema"]["properties"]["source_facts_used"]["items"]["enum"]
    assert "provider_author" not in sent


def test_citing_an_absent_fact_fails_that_sample_and_its_replies_are_kept(claude):
    bad = reading("external", facts=["provider_author"])   # NOTE_FACTS has no provider_author
    claude.queue(reading(quotes=["It took me six hours a week"]), bad, bad)
    result = classify()
    assert result.authorship == "user_authored" and not result.confident
    assert result.reasons == ["source: a sample gave no valid answer"]
    assert len(result.failures) == 1 and result.failures[0]["part"] == 1
    replies = result.failures[0]["replies"]
    assert len(replies) == 2 and replies[0]["tool_input"]["source_facts_used"] == ["provider_author"]
    assert result.detail()["classifier"]["failed_samples"] == 1
    assert "replies" not in json.dumps(result.detail())   # raw replies are not stored with the source


def test_samples_that_disagree_are_not_confident_and_resolve_to_external(claude):
    # tc-p03 in the 2026-10-19 baseline: one reading took a signed outside post as the user's own.
    claude.queue(reading(quotes=["It took me six hours a week"]),
                 reading("external", quotes=["It took me six hours a week"]))
    result = classify()
    assert not result.confident and "source: the samples disagree" in result.reasons
    assert result.authorship == "external" and result.spans == []


def test_samples_that_disagree_on_one_paragraph_keep_it_external(claude):
    claude.queue(reading(quotes=["It took me six hours a week"]),
                 reading(other=[1], quotes=["It took me six hours a week"]))
    result = classify()
    assert not result.confident and result.reasons == ["source: the samples disagree"]
    # paragraph 1, external in one sample, is external; it is the longer one, so the source is too
    assert result.authorship == "external"
    assert [(NOTE[s["start"]:s["end"]], s["authorship"]) for s in result.spans] == [(NOTE.split("\n\n")[1], "user_authored")]


def test_one_failed_sample_is_not_confident(claude):
    claude.queue(reading(quotes=["It took me six hours a week"]), "not json", "{}")
    result = classify()
    assert result.authorship == "user_authored" and not result.confident
    assert result.reasons == ["source: a sample gave no valid answer"]


def test_both_samples_stay_in_the_callers_trace(claude):
    from llm.client import trace_calls
    claude.queue(*[reading(quotes=["It took me six hours a week"])] * 2)
    with trace_calls() as calls:
        classify()
    assert len(calls) == 2


def test_failed_structured_answer_is_none_never_a_guess(claude):
    claude.queue("not json", "{}", "not json", "{}")   # each sample's structured call retries once
    assert classify() is None
    assert len(claude.calls) == 4


def test_empty_text_makes_no_call(claude):
    assert classify(" \n\n ") is None and claude.calls == []


def test_long_source_is_classified_in_parts_and_combined(claude):
    block = "Paragraph text from a long transcript. " * 40
    count = 2 * MAX_PART_CHARS // len(block) + 2
    text = "\n\n".join([block.strip()] * count)
    paras = paragraphs(text)
    groups = parts(paras)
    assert len(groups) == 3
    last_part_first_id = groups[2][0].id
    plain = reading("external", facts=["provider_author"])
    claude.queue(plain, plain, plain, plain,      # parts 1 and 2, two samples each
                 *[reading("external", other=[last_part_first_id], facts=["provider_author"])] * 2)
    result = classify(text, facts=VIDEO_FACTS)
    assert len(claude.calls) == 6
    second = claude.calls[2]["messages"][-1]["content"]
    assert "This is part 2" in second and "OPENING OF THE SOURCE" in second and "[P1]" in second
    assert result.authorship == "external" and result.confident
    flipped = groups[2][0]
    assert result.spans == [{"start": flipped.start, "end": flipped.end, "authorship": "user_authored"}]


def test_one_uncertain_part_makes_the_whole_source_not_confident(claude):
    text = "\n\n".join(["z" * (MAX_PARAGRAPH_CHARS - 1)] * (MAX_PART_CHARS // MAX_PARAGRAPH_CHARS + 2))
    assert len(parts(paragraphs(text))) == 2
    plain = reading("external", facts=["provider_author"])
    claude.queue(plain, plain, *[reading("external", facts=["provider_author"], uncertain=True)] * 2)
    result = classify(text, facts=VIDEO_FACTS)
    assert not result.confident and result.reasons == ["part 2: the model was uncertain"]


def test_detail_records_spans_classifier_version_and_readings(claude):
    claude.queue(*[reading(quotes=["It took me six hours a week"])] * 2)
    detail = classify().detail()
    assert detail["spans"] == []
    assert (detail["classifier"]["name"], detail["classifier"]["version"]) == CLASSIFIER
    assert detail["classifier"]["confident"] is True
    assert detail["classifier"]["samples"] == 2 and len(detail["classifier"]["readings"]) == 2
    assert detail["classifier"]["readings"][0]["evidence_quotes"] == ["It took me six hours a week"]
    json.dumps(detail)   # stored as jsonb


def test_author_context_reads_this_users_profile(fake_db):
    fake_db.tables["profiles"] = [{"id": USER, "data": {"name": "Maya Rao", "role": "Founder"}},
                                  {"id": "someone-else", "data": {"name": "Other", "role": "CTO"}}]
    context = author_context(USER)
    assert (context.name, context.role) == ("Maya Rao", "Founder")


def test_author_context_for_a_business_includes_its_profile_and_built_experience_labels():
    from agents.provenance_agent import author_context_from
    account = {"segment": "business", "business_niche": "real_estate", "business_niche_other": None,
               "business_profile": {"business_name": "Fernleigh Homes", "services": "Selling and letting homes"}}
    nodes = [{"node_type": "work", "entity_name": "Quillmark", "role": "Founder", "start_date": "2024-09",
              "end_date": None, "description": "Building Sieve."}]   # a fixture node: no stored context_label
    context = author_context_from(None, account, nodes)
    assert "Business name: Fernleigh Homes" in context.business and "Selling and letting homes" in context.business
    assert "Founder at Quillmark" in context.experience and "Building Sieve." in context.experience


def test_a_person_account_has_no_business_block(claude):
    from agents.provenance_agent import author_context_from
    context = author_context_from({"name": "Maya Rao", "role": "Founder"}, {"segment": "person"}, [])
    assert context.business == ""
    claude.queue(*[reading(quotes=["It took me six hours a week"])] * 2)
    classify_provenance(NOTE, facts=NOTE_FACTS, author=context, user_id=USER)
    assert "A business account" not in claude.calls[0]["messages"][-1]["content"]


# --- Signatures (v4) -----------------------------------------------------------------------------

SIGNED = NOTE + "\n\nRavi Mehta, lean coach"


def _classify_signed(text=SIGNED, author=AUTHOR):
    return classify_provenance(text, facts=NOTE_FACTS, author=author, user_id=USER)


def test_a_reading_that_names_someone_elses_signature_but_labels_text_own_is_not_confident(claude):
    claude.queue(*[reading(other=[3], quotes=["It took me six hours a week"], signed_by="Ravi Mehta, lean coach")] * 2)
    result = _classify_signed()
    assert not result.confident
    assert any("signed by someone other than the user" in r for r in result.reasons)


def test_someone_elses_signature_on_an_external_reading_is_confident(claude):
    claude.queue(*[reading("external", quotes=["Ravi Mehta, lean coach"], signed_by="Ravi Mehta, lean coach")] * 2)
    result = _classify_signed()
    assert result.confident and result.authorship == "external"


@pytest.mark.parametrize("signature,author,confident", [
    ("Maya Rao", AUTHOR, True),                                        # the user's full name
    ("— maya  rao, founder", AUTHOR, True),                            # case, spacing and role around it
    ("Maya", AUTHOR, False),                                           # a first name alone is asked about
    ("Maya Raoul", AUTHOR, False),                                     # a different name sharing letters
    ("The Fernleigh Homes team", AuthorContext(business_name="Fernleigh Homes"), True),
    ("Brookfield Homes", AuthorContext(business_name="Fernleigh Homes"), False),
])
def test_a_signature_matches_the_user_only_by_full_name(claude, signature, author, confident):
    text = NOTE + "\n\n" + signature
    claude.queue(*[reading(quotes=["It took me six hours a week"], signed_by=signature)] * 2)
    assert _classify_signed(text=text, author=author).confident is confident


def test_a_signature_not_in_the_text_is_not_confident(claude):
    claude.queue(*[reading(quotes=["It took me six hours a week"], signed_by="Maya Rao")] * 2)
    result = classify()
    assert not result.confident and any("signature is not in the text" in r for r in result.reasons)


def test_business_name_comes_from_a_business_account_only():
    from agents.provenance_agent import author_context_from
    business = {"segment": "business", "business_profile": {"business_name": "Fernleigh Homes"}}
    assert author_context_from(None, business, []).business_name == "Fernleigh Homes"
    person = {"segment": "person", "business_profile": {"business_name": "Side Gig"}}
    assert author_context_from({"name": "Maya Rao"}, person, []).business_name == ""
