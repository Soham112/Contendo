"""quality_v1 fixtures and the B1 retrieval scorers. No network, no backend imports."""
import json
from collections import Counter

import pytest

import quality_fixtures as qf
import quality_metrics as qm
from loaders import FixtureError


@pytest.fixture(scope="module")
def cases():
    return qf.load_cases(include_private=False)


def _case(**overrides):
    base = {
        "id": "x-01", "persona": "rf", "split": "dev", "identity": "person", "topic": "t", "context": "",
        "pillar": None, "pillar_details": "", "tone": "casual", "objective": "lesson", "authority": "high",
        "cold_start_tier": 3, "phrasing": "broad", "coverage": "full", "evidence": "first_person",
        "must_use_all": [], "must_use_any": [], "background": [], "off_topic": [], "central_idea": "c",
        "eligible_angles": ["observation"], "ineligible_angles": [], "needs_present": [], "needs_missing": [],
        "do_not_claim": [], "note": "", "label_confidence": "verified",
    }
    return {**base, **overrides}


# --- fixtures -----------------------------------------------------------------

def test_every_synthetic_persona_loads_including_cold_start_states():
    loaded = {s: qf.load_quality_persona(s) for s in qf.SYNTHETIC_SLUGS}
    assert loaded["ni0"].profile is None and not loaded["ni0"].sources
    assert loaded["nb"].profile is None and not loaded["nb"].sources
    assert len(loaded["rf"].sources) == 20


def test_business_personas_have_accounts_and_individuals_do_not_need_one():
    assert {s for s in qf.SYNTHETIC_SLUGS if qf.is_business(s)} == {"re", "fs", "bo", "nb"}
    assert qf.load_account("rf") is None
    assert qf.load_account("bo")["business_niche_other"] == "Mobile bike repair"


def test_public_cases_are_synthetic_verified_and_cover_every_persona(cases):
    assert len(cases) == 52
    assert {c["label_confidence"] for c in cases} == {"verified"}
    assert set(Counter(c["persona"] for c in cases)) == set(qf.SYNTHETIC_SLUGS)


def test_two_whole_personas_are_held_out(cases):
    for slug in ("tc", "fs"):
        assert {c["split"] for c in cases if c["persona"] == slug} == {"holdout"}
    assert {c["split"] for c in cases if c["persona"] == "rf"} == {"dev", "holdout"}


def test_any_of_groups_have_two_or_more_sources(cases):
    assert all(len(c["must_use_any"]) != 1 for c in cases)
    assert next(c for c in cases if c["id"] == "rf-04")["must_use_any"] == ["rf-s02", "rf-s04", "rf-s08"]


def test_own_ids_follow_fixture_memory_context_and_business_notes():
    rf = qf.own_label_ids("rf")
    assert "rf-s02" in rf and "rf-s11" not in rf and "rf-s18" not in rf  # s18 is an observation
    assert "re-bp" in qf.own_label_ids("re")
    assert "nb-02-details" in qf.own_label_ids("nb")


@pytest.mark.parametrize("overrides, error", [
    ({"must_use_any": ["rf-s01"]}, "two or more"),
    ({"must_use_all": ["rf-s01"], "off_topic": ["rf-s01"]}, "also background or off_topic"),
    ({"must_use_all": ["rf-s01"], "must_use_any": ["rf-s01", "rf-s02"]}, "both must_use_all and must_use_any"),
    ({"label_confidence": "metadata_only"}, "only persona me"),
    ({"background": ["rf-s99"]}, "unknown source rf-s99"),
    ({"eligible_angles": ["hot_take"]}, "unknown angle hot_take"),
    ({"coverage": "some"}, "coverage='some'"),
])
def test_case_validation_rejects_bad_labels(overrides, error):
    known = set(qf.source_labels("rf"))
    assert any(error in e for e in qf._case_errors(_case(**overrides), known))


def test_a_valid_case_has_no_errors():
    assert qf._case_errors(_case(must_use_any=["rf-s02", "rf-s04"]), set(qf.source_labels("rf"))) == []


def test_sequences_name_known_personas_and_six_to_eight_topics():
    seq = json.loads((qf.GOLDENS_DIR / "sequences.json").read_text())
    assert set(seq) <= set(qf.SYNTHETIC_SLUGS)
    assert all(6 <= len(topics) <= 8 for topics in seq.values())


def test_users_file_absent_is_allowed_only_when_asked(monkeypatch, tmp_path):
    monkeypatch.setattr(qf, "USERS_FILE", tmp_path / "users.json")
    assert qf.load_quality_users(allow_missing=True) == {}
    with pytest.raises(FixtureError, match="create-users"):
        qf.load_quality_users()


def test_pillar_details_cases_run_as_their_own_user(cases):
    states = qf.details_states()
    assert set(states) == {c["id"] for c in cases if c["pillar_details"]} == {"re-02", "nb-02"}
    assert qf.user_slug(states["re-02"]) == "re-02"
    assert qf.user_slug(next(c for c in cases if c["id"] == "re-01")) == "re"


def test_details_note_counts_as_own_for_business_personas():
    assert "re-02-details" in qf.own_label_ids("re") and not any(i.endswith("-details") for i in qf.own_label_ids("rf"))


# --- retrieval scorecard ---------------------------------------------------------

def test_recall_counts_an_any_of_group_as_one_unit():
    case = _case(must_use_all=["a"], must_use_any=["b", "c"])
    assert qm.recall_at(case, ["c", "x", "a"]) == 1.0
    assert qm.recall_at(case, ["c", "x", "a"], 1) == 0.5
    assert qm.recall_at(case, ["x"]) == 0.0
    assert qm.recall_at(_case(), ["a"]) is None  # nothing required


def test_recall_reports_the_cutoff_and_diagnostic_k():
    r = qm.recall(_case(must_use_all=["a", "b"]), ["x", "a", "y", "z", "b"])
    assert r["cutoff"] == 5 and r["at_cutoff"] == 1.0 and r["pass"] is True
    assert r["at"] == {"1": 0.0, "3": 0.5, "5": 1.0}


def test_mrr_and_its_pass_limit_depend_on_phrasing():
    assert qm.mrr(_case(must_use_all=["a"]), ["x", "y", "a"]) == {"value": 0.333, "first_rank": 3, "pass": True}
    assert qm.mrr(_case(must_use_all=["a"], phrasing="names_project"), ["x", "a"])["pass"] is False
    assert qm.mrr(_case(must_use_any=["a", "b"]), [])["value"] == 0.0
    assert qm.mrr(_case(), ["a"])["value"] is None


def test_precision_counts_unlabelled_for_verified_but_not_metadata_only():
    labels = ["a", qm.UNLABELLED, qm.CONSOLIDATION]
    assert qm.precision(_case(must_use_all=["a"]), labels)["value"] == 0.5
    assert qm.precision(_case(must_use_all=["a"], label_confidence="metadata_only"), labels)["value"] == 1.0
    assert qm.precision(_case(), [])["pass"] is None


def test_business_cases_carry_business_block_and_never_require_the_note(cases):
    business = {c["persona"] for c in cases if qf.is_business(c["persona"])}
    assert all(c.get("business_block") for c in cases if c["persona"] in business)
    assert not any(c.get("business_block") for c in cases if c["persona"] not in business)
    known = set(qf.source_labels("re")) | {"re-bp"}
    flagged = dict(persona="re", identity="business", evidence="business_facts", business_block=True, expected_gate="pass")
    assert qf._case_errors(_case(**flagged, must_use_all=["re-s01"]), known) == []
    assert any("block, not a required source" in e
               for e in qf._case_errors(_case(**flagged, must_use_all=["re-bp"]), known))
    assert any("business_block must be true" in e
               for e in qf._case_errors(_case(**{**flagged, "business_block": False}), known))
    assert any("business_block must be true" in e
               for e in qf._case_errors(_case(business_block=True), set(qf.source_labels("rf"))))


def test_the_profile_note_is_neutral_for_precision_in_business_block_cases():
    labels = ["re-s01", "re-bp", "x"]
    assert qm.precision(_case(persona="re", must_use_all=["re-s01"], business_block=True), labels)["value"] == 0.5
    assert qm.precision(_case(persona="re", must_use_all=["re-s01"]), labels)["value"] == 0.333


def test_off_topic_rate_and_list():
    assert qm.off_topic(_case(off_topic=["o"]), ["a", "o"]) == {"value": ["o"], "rate": 0.5, "pass": False}


def test_own_share_applies_only_to_topics_that_name_a_project():
    own = frozenset({"a"})
    assert qm.own_share(_case(), ["a"], own)["pass"] is None
    named = _case(phrasing="names_project")
    assert qm.own_share(named, ["a", "x"], own)["pass"] is True
    assert qm.own_share(named, ["a", "x", "y"], own)["pass"] is False
    assert qm.own_share(named, [], own) == {"value": 0.0, "pass": False}
    assert qm.own_share(named, ["a"], None)["pass"] is None  # metadata_only


def test_gate_accuracy_by_labelled_coverage():
    assert qm.gate_accuracy(_case(coverage="none"), "low_coverage") is True
    assert qm.gate_accuracy(_case(coverage="full"), "low_coverage") is False
    assert qm.gate_accuracy(_case(coverage="partial"), "pass") is None


def test_hybrid_reliability_fails_on_fallback_or_truncated_corpus():
    full = {"ran": True, "corpus_size": 14, "library_chunks": 14}
    assert qm.hybrid_reliability(full, "hybrid", 1)["pass"] is True
    assert qm.hybrid_reliability(full, "flat_fallback", 1)["pass"] is False
    assert qm.hybrid_reliability({"ran": True, "corpus_size": 1000, "library_chunks": 1101}, "hybrid", 1)["pass"] is False
    assert qm.hybrid_reliability({"ran": False, "error": "boom", "library_chunks": 9}, "hybrid", 1)["pass"] is False
    assert qm.hybrid_reliability({"ran": False, "corpus_size": 0, "library_chunks": 0}, "hybrid", 1)["pass"] is None
    assert qm.hybrid_reliability(full, "hybrid", 2)["attempts"] == 2  # recorded, not hidden


def test_score_case_scores_the_drafter_and_keeps_pre_gate_recall():
    case = _case(must_use_all=["a"])
    scored = qm.score_case(case, [], ["a"], None, "low_coverage", {"ran": True, "corpus_size": 3, "library_chunks": 3})
    assert scored["recall"]["pass"] is False and scored["recall_before_gate"]["pass"] is True
    rates = qm.pass_rates([scored])
    assert rates["recall"] == (0, 1) and rates["hybrid_reliability"] == (1, 1) and rates["gate_accuracy"] == (0, 1)
    assert qm.means([scored])["mrr"] == 0.0 and qm.means([scored])["off_topic_rate"] is None


def test_every_business_case_requires_expected_gate(cases):
    for case in cases:
        if not case.get("business_block"):
            continue
        assert case["expected_gate"] in {"pass", "profile_only", "low_coverage"}
        changed = dict(case)
        del changed["expected_gate"]
        assert any("expected_gate" in e for e in qf._case_errors(changed, set()))


@pytest.mark.parametrize("expected", ["pass", "profile_only", "low_coverage"])
def test_business_gate_accuracy_uses_explicit_label_even_for_partial(expected):
    case = _case(business_block=True, expected_gate=expected, coverage="partial")
    assert qm.gate_accuracy(case, expected) is True
    assert qm.gate_accuracy(case, "skipped_first_post") is False


def test_rescore_saved_updates_business_gate_without_changing_rankings(tmp_path, monkeypatch):
    import importlib
    import sys
    import types
    fake_env = types.ModuleType('env')
    fake_env.CONFIG = types.SimpleNamespace(project_ref='test-project')
    monkeypatch.setitem(sys.modules, 'env', fake_env)
    sys.modules.pop('quality_retrieval', None)
    retrieval = importlib.import_module('quality_retrieval')
    case = _case(persona='bo', business_block=True, expected_gate='profile_only')
    row = {'id': case['id'], 'persona': 'bo', 'split': 'dev', 'label_confidence': 'verified',
           'ranked_chunks': [], 'drafted': [], 'gate': {'decision': 'profile_only'},
           'retrieval_path': 'hybrid', 'attempts': 1,
           'scores': qm.score_case(case, [], [], frozenset(), 'profile_only', {}, 'hybrid', 1)}
    row['scores']['gate_accuracy'] = None  # old label did not score this case
    source = tmp_path / 'original' / 'runs.jsonl'
    source.parent.mkdir()
    original = json.dumps(row) + '\n'
    source.write_text(original)
    monkeypatch.setattr(qf, 'load_cases', lambda: [case])
    monkeypatch.setattr(qf, 'own_label_ids', lambda slug: frozenset())
    monkeypatch.setattr(retrieval, 'RESULTS_DIR', tmp_path / 'results')
    monkeypatch.setattr(retrieval, 'PRIVATE_RESULTS_DIR', tmp_path / 'private')
    retrieval.rescore_saved(source, 'rescored')
    result = json.loads((tmp_path / 'results/rescored/runs.jsonl').read_text())
    assert result['scores']['gate_accuracy'] is True
    assert result['ranked_chunks'] == row['ranked_chunks'] and result['gate'] == row['gate']
    assert source.read_text() == original
    assert 'business · dev' in (tmp_path / 'results/rescored/report.md').read_text()
    sys.modules.pop('quality_retrieval', None)


def test_profile_writability_revision_preserves_review_labels_and_blocks_kitchen_case(cases):
    by_id = {case['id']: case for case in cases}
    assert by_id['nb-04']['expected_gate'] == 'low_coverage'
    assert by_id['re-05']['expected_gate'] == 'low_coverage'
    assert by_id['fs-06']['expected_gate'] == 'low_coverage'


def test_free_paired_prompt_measurement_preserves_new_run_scores(tmp_path, monkeypatch):
    import importlib
    import os
    import sys
    import types
    fake_env = types.ModuleType('env')
    fake_env.CONFIG = types.SimpleNamespace(project_ref='test-project')
    monkeypatch.setitem(sys.modules, 'env', fake_env)
    monkeypatch.setitem(sys.modules, 'quality_seed', types.SimpleNamespace(details_note_for=lambda *args: None))
    sys.modules.pop('quality_retrieval', None)
    retrieval = importlib.import_module('quality_retrieval')
    case = _case(persona='bo', business_block=True, expected_gate='profile_only')
    probe = types.SimpleNamespace(state={})
    seen = []

    def retrieve(*args):
        enabled = os.environ['BUSINESS_BLOCK_ENABLED'] == '1'
        seen.append(enabled)
        probe.state = {'ran': True, 'library_chunks': 1 if enabled else 2, 'corpus_size': 1 if enabled else 2}
        return {'retrieval_bundle': {'chunks': []}, 'coverage_gate': {'decision': 'profile_only' if enabled else 'pass'},
                'retrieval_path': 'hybrid', 'enabled': enabled}, 1

    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1')
    monkeypatch.setattr(retrieval, '_retrieve', retrieve)
    monkeypatch.setattr(retrieval, '_labeller', lambda *args: lambda *args: 'unused')
    monkeypatch.setattr(retrieval, 'measure_prompt', lambda state, count: {
        'business_block_present': state['enabled'], 'prompt_tokens': 100 if state['enabled'] else 150})
    monkeypatch.setattr(qf, 'own_label_ids', lambda slug: frozenset())
    result = retrieval.run_case(case, 'user', None, probe, None, count_tokens=True)
    assert seen == [True, False]
    assert os.environ['BUSINESS_BLOCK_ENABLED'] == '1'
    assert result['gate']['decision'] == 'profile_only'
    assert result['scores']['hybrid_reliability']['library_chunks'] == 1
    assert result['scores']['gate_accuracy'] is True
    assert result['prompt_check']['prompt_token_delta'] == -50
    assert result['prompt_check']['baseline_gate'] == 'pass'
    sys.modules.pop('quality_retrieval', None)
