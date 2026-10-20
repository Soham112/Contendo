"""The provenance test set and its scores (step 3.3). No network, no paid calls."""

import pytest

import provenance_fixtures as pf
import provenance_metrics as pm
from loaders import FixtureError, parse_authorship

OWN, EXT = pm.OWN, pm.EXTERNAL


# --- The test set --------------------------------------------------------------------------------

def test_every_case_is_labelled_and_ids_are_unique():
    cases = pf.load_cases()
    assert all(c.authorship in pm.LABELS for c in cases)
    assert len({c.id for c in cases}) == len(cases)


def test_both_labels_both_splits_and_mixed_cases_are_present():
    cases = pf.load_cases()
    for split in pf.SPLITS:
        in_split = [c for c in cases if c.split == split]
        assert {c.authorship for c in in_split} == set(pm.LABELS), split
    assert any(c.authorship_other for c in cases)


def test_the_hold_out_is_only_cases_written_after_the_first_baseline():
    """The first hold-out was read to diagnose the 2026-10-19 baseline, so it is dev now."""
    cases = pf.load_cases()
    holdout = {c.id for c in cases if c.split == "holdout"}
    assert all(c.origin == "provenance_v1" for c in cases if c.id in holdout)
    seen = {"tc-s01", "tc-p03", "rf-p09", "rf-p11", "fs-p02", "re-p03"}
    assert not holdout & seen and len(holdout) == 12


def test_every_header_agrees_with_the_classifier_paragraphs(backend):
    """authorship_other names real paragraphs, and the header label covers most
    of the text, as the backend splits it."""
    from utils.provenance_spans import paragraphs
    for case in pf.load_cases():
        sizes = {p.id: p.end - p.start for p in paragraphs(case.content)}
        pm.paragraph_truth(case.authorship, case.authorship_other, sizes)


def test_rf_s18_first_person_observation_is_the_users_own():
    assert next(c for c in pf.load_cases() if c.id == "rf-s18").authorship == OWN


def test_persona_details_are_what_the_author_context_reads():
    profile, account, nodes = pf.persona_details("re")
    assert profile is None and account["business_profile"]["business_name"] == "Fernleigh Homes"
    profile, account, nodes = pf.persona_details("rf")
    assert profile["name"] == "Dara Okafor" and account is None and nodes[0]["entity_name"] == "Quillmark"


@pytest.mark.parametrize("header, error", [
    ({"authorship": "mine"}, "authorship must be one of"),
    ({"authorship": OWN, "authorship_other": "2, x"}, "comma-separated"),
    ({"authorship_other": "2"}, "needs authorship"),
])
def test_bad_authorship_headers_are_refused(tmp_path, header, error):
    with pytest.raises(FixtureError, match=error):
        parse_authorship(tmp_path / "x.md", header)


def test_authorship_other_is_parsed_as_paragraph_numbers(tmp_path):
    assert parse_authorship(tmp_path / "x.md", {"authorship": EXT, "authorship_other": "3, 1"}) == (EXT, (3, 1))


# --- Paragraph labels ----------------------------------------------------------------------------

def test_paragraph_truth_flips_listed_paragraphs():
    assert pm.paragraph_truth(OWN, [2], {1: 50, 2: 10, 3: 50}) == {1: OWN, 2: EXT, 3: OWN}


def test_paragraph_truth_refuses_a_header_that_does_not_cover_most_of_the_text():
    with pytest.raises(ValueError, match="does not cover most"):
        pm.paragraph_truth(OWN, [2], {1: 10, 2: 50})
    with pytest.raises(ValueError, match="do not exist"):
        pm.paragraph_truth(OWN, [4], {1: 10})


def test_a_tie_is_external():
    assert pm.source_label({1: OWN, 2: EXT}, {1: 5, 2: 5}) == EXT


def test_predicted_paragraphs_take_their_span_label():
    paras = [(1, 0, 10), (2, 12, 20), (3, 22, 30)]
    spans = [{"start": 12, "end": 20, "authorship": OWN}]
    assert pm.predicted_paragraphs(EXT, spans, paras) == {1: EXT, 2: OWN, 3: EXT}


# --- Scores --------------------------------------------------------------------------------------

def rec(cid, truth, truth_p, result=None, split="dev"):
    return {"id": cid, "split": split, "truth": truth, "truth_paragraphs": truth_p,
            "sizes": {i: 10 for i in truth_p}, "result": result}


def answer(label, confident, paragraphs):
    return {"authorship": label, "confident": confident, "paragraphs": paragraphs}


def test_outside_paragraph_applied_as_own_is_counted_even_inside_an_own_source():
    records = [
        rec("a", OWN, {"1": OWN, "2": EXT, "3": OWN}, answer(OWN, True, {"1": OWN, "2": OWN, "3": OWN})),
        rec("b", EXT, {"1": EXT}, answer(OWN, True, {"1": OWN})),
        rec("c", EXT, {"1": EXT}, answer(OWN, False, {"1": OWN})),   # not confident: the user is asked
    ]
    scores = pm.score(records)
    assert scores["external_applied_as_own"] == 2
    assert scores["external_applied_as_own_where"] == ["a#P2", "b#P1"]
    assert pm.verdicts(scores)["external_applied_as_own"] is False


def test_rates_confusion_and_failures():
    records = [
        rec("a", OWN, {"1": OWN}, answer(OWN, True, {"1": OWN})),
        rec("b", OWN, {"1": OWN}, answer(EXT, True, {"1": EXT})),
        rec("c", EXT, {"1": EXT}, answer(EXT, True, {"1": EXT})),
        rec("d", EXT, {"1": EXT}, None),
    ]
    s = pm.score(records)
    assert s["failed"] == 1 and s["applied_automatically"] == 0.75
    assert s["own_applied_as_external"] == 0.5
    assert s["confusion"][OWN] == {OWN: 1, EXT: 1, "failed": 0}
    assert s["precision"][EXT] == 0.5 and s["recall"][EXT] == 0.5
    assert s["external_applied_as_own"] == 0
    assert pm.verdicts(s) == {"external_applied_as_own": True, "own_applied_as_external": False,
                              "applied_automatically": False, "run_agreement": None}


def test_mixed_paragraph_recall_counts_only_minority_paragraphs():
    records = [rec("a", OWN, {"1": OWN, "2": EXT, "3": EXT, "4": OWN},
                   answer(OWN, False, {"1": OWN, "2": EXT, "3": OWN, "4": OWN}))]
    assert pm.score(records)["mixed_paragraph_recall"] == 0.5


def test_run_agreement_compares_label_confidence_and_paragraphs():
    a = {"x": answer(OWN, True, {"1": OWN}), "y": answer(EXT, True, {"1": EXT}), "z": None}
    b = {"x": answer(OWN, True, {1: OWN}), "y": answer(EXT, False, {"1": EXT}), "z": None, "w": None}
    assert pm.agreement(a, b) == pytest.approx(2 / 3)
    assert pm.agreement({}, b) is None
