"""The ablation harness: the variant guard, the shared price table, both length
counts in the report, and the blind read's make/score round trip. No network,
no database; the backend modules imported here are its pure ones (price table,
word counts)."""

import json

import pytest

import ablation
import blind
import eval_config as config
import guard
from guard import EnvGuardError

VARIANTS = ("A", "B", "C", "B-Opus", "C-Opus")


# --- The env guard and PIPELINE_VARIANT ----------------------------------------------------

def _bootstrap(env_path):
    environ: dict[str, str] = {}
    guard.bootstrap(env_file=env_path, environ=environ, modules={}, sys_path=[])
    return environ


def test_the_guard_reads_the_variants_from_the_backend(backend):
    from config import features

    assert guard.pipeline_variants() == features.PIPELINE_VARIANTS == VARIANTS


@pytest.mark.parametrize("value", ["D", "b", "B-opus", "A,B"])
def test_an_unknown_pipeline_variant_is_refused(env_file, value):
    with pytest.raises(EnvGuardError, match="not a pipeline variant"):
        _bootstrap(env_file(PIPELINE_VARIANT=value))


@pytest.mark.parametrize("value", VARIANTS)
def test_a_known_pipeline_variant_reaches_the_backend_environment(env_file, value):
    assert _bootstrap(env_file(PIPELINE_VARIANT=value))["PIPELINE_VARIANT"] == value


def test_without_one_the_variable_is_set_empty_so_no_env_file_can_fill_it(env_file):
    assert _bootstrap(env_file())["PIPELINE_VARIANT"] == ""


# --- One price table ---------------------------------------------------------------------

CALLS = [
    {"event_type": "archetype", "model": "claude-haiku-4-5-20251001", "input_tokens": 1_000_000, "output_tokens": 0},
    {"event_type": "generate", "model": "claude-opus-5-5", "input_tokens": 0, "output_tokens": 1_000_000,
     "thinking_tokens": 250_000},
]


def test_eval_costs_come_from_the_backend_price_table(backend, monkeypatch):
    from llm import pricing

    summary = ablation.summarize_llm_calls(CALLS, pricing.call_cost)
    assert (summary["calls"], summary["input_tokens"], summary["output_tokens"], summary["thinking_tokens"]) == (
        2, 1_000_000, 1_000_000, 250_000)
    assert summary["cost_usd"] == pytest.approx(1.00 + 20.00)
    assert summary["by_model"]["claude-opus-5-5"]["cost_usd"] == pytest.approx(20.00)

    monkeypatch.setitem(pricing.PRICES, "claude-opus-5-5", pricing.Price(8.00, 40.00))
    assert ablation.summarize_llm_calls(CALLS, pricing.call_cost)["cost_usd"] == pytest.approx(1.00 + 40.00)


def test_the_evals_keep_no_price_table_of_their_own():
    assert not hasattr(config, "PRICES_PER_MTOK") and not hasattr(config, "call_cost")
    for script in ("run.py", "judge.py", "instrument.py", "review_regression.py"):
        assert "from llm.pricing import call_cost" in (config.EVALS_DIR / script).read_text(), script


# --- The report -----------------------------------------------------------------------

TARGET = {"min_words": 5, "max_words": 8, "basis": "length_setting"}
# Six words of prose under a heading of four tokens: ten by count_words, six by prose_word_count.
HEADED = "## A short heading\n\nSix words of prose are here."


def _row(golden_id, record, seconds=10.0, cost=0.02, **extra):
    return {"golden_id": golden_id, "status": "ok", "seconds": seconds, "record": record,
            "pipeline": {"calls": 3, "input_tokens": 4000, "output_tokens": 500, "thinking_tokens": 0,
                         "cost_usd": cost, "by_model": {"claude-sonnet-4-6": {}}}, **extra}


def _variant(name, rows, scores=None, instrument=()):
    return {"meta": {"variant": name, "run_id": f"run-{name}", "git": {"commit": "abc1234"}}, "runs": rows,
            "scores": scores or {}, "instrument": list(instrument)}


def test_the_report_measures_length_with_both_counts(backend):
    from utils.citations import prose_word_count
    from utils.formatters import count_words

    counters = {"count_words": count_words, "prose_word_count": prose_word_count}
    record = ablation.post_record({"final_post": HEADED, "length_target": TARGET}, [], counters)

    assert record["length"] == {"count_words": {"words": 10, "status": "over_length"},
                                "prose_word_count": {"words": 6, "status": "ok"}}
    report = ablation.build_ablation("t", [_variant("A", [_row("g1", record)])])
    assert "| length violations, count_words | 1 over, 0 under (of 1) |" in report
    assert "| length violations, prose_word_count | 0 over, 0 under (of 1) |" in report


def _reviewed(route_fixes, outcome, **extra):
    review = {"outcome": outcome, "remaining": [], "unreviewed": [], "removed": [], **extra}
    if route_fixes is not None:
        review["fixes"] = {"route": route_fixes}
    return ablation.post_record({"final_post": "One two three four five six.", "length_target": TARGET, "review": review},
                                [], {"count_words": lambda t: len(t.split()), "prose_word_count": lambda t: len(t.split())})


def test_the_report_gives_route_rates_outcomes_removed_content_and_the_labels():
    records = [
        _reviewed(None, "clean"),
        _reviewed("none", "fixed", removed=[{"kind": "motive"}, {"kind": "motive"}, {"kind": "feeling_or_reaction"}]),
        _reviewed("targeted", "issues_remain",
                  remaining=[{"type": "not_in_sources", "origin": "review"}, {"type": "over_length", "origin": "checks"}]),
        _reviewed("full", "fixed", redraft_truncated={"max_tokens": 1, "output_tokens": 1}),
    ]
    assert [r["route"] for r in records] == ["none", "code-only", "targeted", "full"]
    assert records[2]["remaining"] == {"not_in_sources": 1}            # the review's issues only, not the checks'
    rows = [_row(f"g{n}", record, seconds=float(n)) for n, record in enumerate(records, 1)]
    instrument = [{"golden_id": "g1", "status": "ok", "source": "s", "outcome": "issues",
                   "acting": {"not_in_sources": 2, "wrong_citation": 5}}]

    report = ablation.build_ablation("t", [_variant("B", rows, instrument=instrument)], audit={"of": 10, "marked": 10, "correct": 7})

    assert "none 25% (1), code-only 25% (1), targeted 25% (1), full 25% (1)" in report
    assert "clean 1, fixed 2, issues_remain 1, not_reviewed 0" in report
    assert "redraft_truncated 1" in report
    assert "feeling_or_reaction 1, motive 2" in report
    assert "| wall time p50 / p90, s | 2.0 / 4.0 |" in report
    assert "2 on 1 post(s) | not_in_sources 2 | wrong_citation 5 |" in report
    assert "same reviewer as B, so biased in B's favour" in report
    assert "low precision, not decisive" in report
    assert "UNRELIABLE: 7 of 10 audited findings judged correct" in report


def test_the_instrument_counts_the_last_line_per_post_and_never_a_review_that_did_not_happen():
    record = _reviewed(None, "clean")
    lines = [
        {"golden_id": "g1", "status": "not_reviewed", "source": "s", "outcome": "not_reviewed", "acting": {}},
        {"golden_id": "g1", "status": "ok", "source": "s", "outcome": "issues", "acting": {"off_topic": 1}},   # the retry
        {"golden_id": "g2", "status": "not_reviewed", "source": "s", "outcome": "not_reviewed", "acting": {}},
        {"golden_id": "g3", "status": "error", "error": "trace not found"},
    ]

    report = ablation.build_ablation("t", [_variant("C", [_row("g1", record)], instrument=lines)])

    assert "| C | s | 1 (1 not reviewed, 1 failed) | 1 on 1 post(s) | off_topic 1 | – |" in report


def test_the_full_run_report_says_why_the_instrument_was_not_run_and_shows_spend_and_the_regression_set():
    record = _reviewed(None, "clean")
    spend_ledger = {"cap_usd": 14.0, "spent_usd": 14.31, "reached": True, "entries": [],
                    "stops": ["run r5 (variant C-Opus) before ds-07: 6 of 27 goldens run"]}
    regression = [{"id": "flag-added-motive", "model": "claude-sonnet-4-6", "passed": True},
                  {"id": "no-flag-authors-analogy", "model": "claude-sonnet-4-6", "passed": False}]

    report = ablation.build_ablation("full", [_variant("A", [_row("g1", record)])], spend=spend_ledger, regression=regression)

    assert "Not run for this ablation." in report and "biased in B's favour" in report
    assert "| variant | from | posts |" not in report
    assert "Spend: **$14.31** measured, against a cap of $14.00" in report
    assert "**Stopped at the spend cap** run r5 (variant C-Opus) before ds-07: 6 of 27 goldens run." in report
    assert "1 of 2 cases passed on `claude-sonnet-4-6` (failed: no-flag-authors-analogy)" in report
    assert "not part of the decision" in report


def test_the_full_ablation_leaves_b_out_and_the_report_opens_with_the_decision_rules():
    assert config.ABLATION_VARIANTS == ("A", "C", "B-Opus", "C-Opus")
    assert set(config.ABLATION_VARIANTS) <= set(VARIANTS) and config.EVAL_SPEND_CAP_USD == 14.0

    report = ablation.build_ablation("full", [_variant("A", [_row("g1", _reviewed(None, "clean"))])])

    rules = report.index("## Decision rules (fixed 2026-10-10, before the full run)")
    assert report.index("# Ablation: full") < rules < report.index("Judges are the same") < report.index("## Runs")
    assert len(config.DECISION_RULES) == 3
    for number, rule in enumerate(config.DECISION_RULES, 1):
        assert f"{number}. {rule}" in report
    assert config.DECISION_TIEBREAK in report and config.DECISION_NOTE in report
    assert rules < report.index(config.DECISION_FEWER_RANKED) < report.index(config.DECISION_AUDIT_BELOW) < report.index("## Runs")
    assert "rule 1's judge criterion is dropped. Rules 1 and 2" not in report        # no audit yet: nothing is dropped
    assert rules < report.index(config.DECISION_TIEBREAK) < report.index(config.DECISION_NOTE) < report.index("## Runs")


def test_the_rules_are_pinned_to_counts_out_of_the_blind_reads_ten_goldens():
    first, second, third = config.DECISION_RULES

    assert config.BLIND_GOLDENS == 10
    assert "at most 1 below B-Opus AND" in first and "B-Opus is ranked above C-Opus in 6 or fewer of the 10 goldens" in first
    assert "ranked above C-Opus in 7 or more of the 10 goldens" in second
    assert "C or C-Opus is ranked above A in at least 5 of the 10 goldens" in third
    assert "excluded from both variants' pass counts equally" in config.DECISION_TIEBREAK
    assert "B-Opus becomes the default" in config.DECISION_TIEBREAK and "I1" in config.DECISION_TIEBREAK
    assert "practical bar, not a statistical test" in config.DECISION_NOTE
    assert [(first, second) for first, second, _ in config.BLIND_HEAD_TO_HEAD] == [
        ("B-Opus", "C-Opus"), ("C", "A"), ("C-Opus", "A")]
    # the proportions are the same thresholds: 7, 6 and 5 of 10
    assert (config.RULE_2_CLEARLY_SHARE, config.RULE_1_LIMIT_SHARE, config.RULE_3_SHARE) == (7 / 10, 6 / 10, 5 / 10)
    assert "at least 70%" in config.DECISION_FEWER_RANKED and "at most 60%" in config.DECISION_FEWER_RANKED
    assert "at least 50%" in config.DECISION_FEWER_RANKED and "every variant produced a post" in config.DECISION_FEWER_RANKED
    assert "below 8 of 10" in config.DECISION_AUDIT_BELOW and "tiebreak does not apply" in config.DECISION_AUDIT_BELOW


def test_score_gives_the_head_to_head_counts_the_rules_read():
    full = [v for v in _blind_variants() if v["variant"] in config.ABLATION_VARIANTS]
    text, key = blind.make_read(full, GOLDENS, seed=7)
    # In 7 goldens the reader puts B-Opus first and A last; in the other 3, C-Opus first and A second.
    usual, other = ["B-Opus", "C-Opus", "C", "A"], ["C-Opus", "A", "B-Opus", "C"]
    for number, (golden_id, labels) in enumerate(sorted(key["goldens"].items())):
        order = usual if number < 7 else other
        ranking = " > ".join(sorted(labels, key=lambda label: order.index(labels[label])))
        text = text.replace(f"ranking[{golden_id}]: ", f"ranking[{golden_id}]: {ranking}")

    result = blind.score_read(text, key)

    assert result["ranked"] == 10
    assert [(p["first"], p["second"], p["first_above"], p["second_above"], p["goldens"], p["first_share"])
            for p in result["head_to_head"]] == [
        ("B-Opus", "C-Opus", 7, 3, 10, 0.7), ("C", "A", 7, 3, 10, 0.7), ("C-Opus", "A", 10, 0, 10, 1.0)]
    b_vs_c, c_vs_a, _ = result["head_to_head"]
    assert [(c["decides"], c["condition"], c["met"]) for c in b_vs_c["checks"]] == [
        ("rule 2 (B-Opus clearly above)", "at least 70%", True), ("rule 1's blind-read condition", "at most 60%", False)]
    assert [(c["condition"], c["met"]) for c in c_vs_a["checks"]] == [("at least 50%", True)]
    assert result["variants"]["B-Opus"]["mean_rank"] == pytest.approx((7 * 1 + 3 * 3) / 10)
    report = ablation.build_ablation("full", [_variant("A", [_row("g1", _reviewed(None, "clean"))])], blind=result)
    assert "| B-Opus vs C-Opus | 7 | 70% | 3 | 10 | rule 2 (B-Opus clearly above): at least 70%, met; " in report
    assert "| C-Opus vs A | 10 | 100% | 0 | 10 | rule 3: at least 50%, met |" in report
    assert "a practical bar, not a statistical test" in report.split("## Blind read")[1]


@pytest.mark.parametrize("above,ranked,rule_2,rule_1", [
    (7, 10, True, False), (6, 10, False, True),          # the counts the rules name
    (6, 9, False, False),                                # 67%: not clearly above, and over rule 1's 60% limit
    (7, 9, True, False), (5, 9, False, True),            # 78% and 56%
    (5, 8, False, False), (3, 5, False, True), (4, 5, True, False),
])
def test_with_fewer_than_ten_ranked_the_thresholds_are_proportions(above, ranked, rule_2, rule_1):
    _, _, checks = config.BLIND_HEAD_TO_HEAD[0]

    pair = blind.head_to_head("B-Opus", "C-Opus", above, ranked, checks)

    assert pair["first_share"] == above / ranked
    assert [check["met"] for check in pair["checks"]] == [rule_2, rule_1]


@pytest.mark.parametrize("above,ranked,retired", [(5, 10, True), (4, 10, False), (4, 8, True), (4, 9, False), (5, 9, True)])
def test_rule_three_is_at_least_half_of_those_ranked(above, ranked, retired):
    _, _, checks = config.BLIND_HEAD_TO_HEAD[1]

    assert [check["met"] for check in blind.head_to_head("C", "A", above, ranked, checks)["checks"]] == [retired]


def test_nothing_ranked_meets_no_condition_and_fails_none():
    _, _, checks = config.BLIND_HEAD_TO_HEAD[0]

    pair = blind.head_to_head("B-Opus", "C-Opus", 0, 0, checks)

    assert pair["first_share"] is None and [check["met"] for check in pair["checks"]] == [None, None]


def test_the_read_never_includes_a_golden_a_variant_has_no_post_for():
    full = [v for v in _blind_variants() if v["variant"] in config.ABLATION_VARIANTS]
    incomplete = sorted(GOLDENS)[:3]
    for golden_id in incomplete:                          # e.g. a truncated or refused C-Opus draft
        del full[-1]["posts"][golden_id]

    text, key = blind.make_read(full, GOLDENS, seed=7)

    assert len(key["goldens"]) == config.BLIND_GOLDENS == 10              # 11 complete goldens were left to choose from
    assert not set(incomplete) & set(key["goldens"])
    for golden_id in sorted(GOLDENS)[3:6]:                                # now only 8 are complete: the read has 8
        del full[0]["posts"][golden_id]
    _, fewer = blind.make_read(full, GOLDENS, seed=7)
    assert len(fewer["goldens"]) == 8


@pytest.mark.parametrize("audit,dropped", [
    (None, False), ({"of": 10, "marked": 10, "correct": 8}, False), ({"of": 10, "marked": 6, "correct": 3}, False),
    ({"of": 10, "marked": 10, "correct": 7}, True),
])
def test_a_failed_judge_audit_is_stated_at_the_top_with_what_it_drops(audit, dropped):
    report = ablation.build_ablation("full", [_variant("A", [_row("g1", _reviewed(None, "clean"))])], audit=audit)

    statement = ("rule 1's judge criterion is dropped. Rules 1 and 2 are decided by the blind read alone, and the "
                 "tiebreak does not apply.**")
    assert ablation.audit_failed(audit) is dropped
    assert (statement in report) is dropped
    if dropped:
        assert "**The judge audit came back at 7 of 10, below 8:" in report
        assert report.index("The judge audit came back") < report.index("## Runs")


def test_head_to_head_counts_only_goldens_that_were_ranked_and_pairs_that_are_in_the_read():
    without_c = [v for v in _blind_variants() if v["variant"] in ("A", "B-Opus", "C-Opus")]
    text, key = blind.make_read(without_c, GOLDENS, seed=7)
    golden_id, labels = sorted(key["goldens"].items())[0]
    ranking = " > ".join(sorted(labels, key=lambda label: ["C-Opus", "B-Opus", "A"].index(labels[label])))

    result = blind.score_read(text.replace(f"ranking[{golden_id}]: ", f"ranking[{golden_id}]: {ranking}"), key)

    assert [(p["first"], p["second"], p["first_above"], p["second_above"], p["goldens"]) for p in result["head_to_head"]] == [
        ("B-Opus", "C-Opus", 0, 1, 1), ("C-Opus", "A", 1, 0, 1)]


def test_the_judged_cell_gives_the_pass_count_the_first_rule_reads():
    def scored(golden_id, score):
        return {"golden_id": golden_id, "metric": "unsupported_specifics", "judge_model": "SONNET", "status": "ok",
                "score": score, "success": score >= config.THRESHOLDS["unsupported_specifics"]}
    scores = {"SONNET": [scored("g1", 1.0), scored("g2", 0.9), scored("g3", 0.6),
                         {**scored("g4", 0.0), "status": "error", "score": None, "success": None}]}

    report = ablation.build_ablation("t", [_variant("C-Opus", [_row("g1", _reviewed(None, "clean"))], scores=scores)])

    assert "| 0.83 (2 of 3 pass, 1 errored) |" in report


@pytest.mark.parametrize("audit,label", [
    (None, "not audited yet"),
    ({"of": 10, "marked": 4, "correct": 4}, "audit incomplete (4 of 10 marked)"),
    ({"of": 10, "marked": 10, "correct": 8}, "reliable: 8 of 10 audited findings judged correct"),
])
def test_the_audit_label(audit, label):
    assert ablation.audit_label(audit) == label


def test_tokens_per_word_leaves_thinking_out():
    outputs = {"final_post": "x", "length_target": None, "source_index": {},
               "draft_history": [{"node": "draft", "text": "one two three four [[S1]]"}]}
    calls = [{"event_type": "generate", "model": "claude-opus-5-5", "output_tokens": 110, "thinking_tokens": 100,
              "stop_reason": "end_turn"}]

    draft = ablation.post_record(outputs, calls, {"count_words": lambda t: len(t.split()),
                                                  "prose_word_count": lambda t: len(t.split())})["draft"]

    assert (draft["marked_words"], draft["tokens_per_word"], draft["thinking_tokens"]) == (5, 2.0, 100)


def test_percentile_is_nearest_rank():
    assert ablation.percentile([], 50) is None
    assert [ablation.percentile([5, 1, 3, 2, 4, 6], p) for p in (50, 90, 100)] == [3, 6, 6]


# --- Blind read and judge audit ---------------------------------------------------------

GOLDENS = {f"g{n:02d}": {"id": f"g{n:02d}", "topic": f"Topic {n}", "context": ""} for n in range(1, 15)}


def _blind_variants(scores=None):
    return [{"variant": name, "run_id": f"run-{name}",
             "posts": {gid: {"golden_id": gid, "post": f"## A heading in the post\n\nnote: by {name} for {gid}",
                             "sources": [{"id": "S1", "title": "T", "text": "source text"}], "profile_text": "profile"}
                       for gid in GOLDENS},
             "scores": (scores or {}).get(name, {})} for name in VARIANTS]


def test_make_is_seeded_and_hides_the_variant(monkeypatch):
    text, key = blind.make_read(_blind_variants(), GOLDENS, seed=7)
    again, same_key = blind.make_read(_blind_variants(), GOLDENS, seed=7)
    _, other_key = blind.make_read(_blind_variants(), GOLDENS, seed=8)

    assert (text, key) == (again, same_key) and key != other_key
    assert len(key["goldens"]) == config.BLIND_GOLDENS
    assert key["labels"] == list(config.BLIND_LABELS) and len(config.BLIND_LABELS) == len(VARIANTS)
    for labels in key["goldens"].values():
        assert tuple(labels) == config.BLIND_LABELS and sorted(labels.values()) == sorted(VARIANTS)
    assert len({tuple(labels.values()) for labels in key["goldens"].values()}) > 1     # shuffled per golden
    assert not any(f"### {name}" in text for name in VARIANTS)


def test_make_then_score_round_trips_through_the_key():
    text, key = blind.make_read(_blind_variants(), GOLDENS, seed=7)
    order = {"B": 1, "B-Opus": 2, "C-Opus": 3, "C": 4, "A": 5}        # the reader's true preference, every time
    unranked = sorted(key["goldens"])[-1]
    for golden_id, labels in key["goldens"].items():
        if golden_id == unranked:
            continue
        ranking = " > ".join(sorted(labels, key=lambda label: order[labels[label]]))
        text = text.replace(f"ranking[{golden_id}]: ", f"ranking[{golden_id}]: {ranking}")
    first = sorted(key["goldens"])[0]
    text = text.replace(f"note[{first}]: ", f"note[{first}]: W has an orphaned sentence")

    result = blind.score_read(text, key)

    assert (result["goldens"], result["ranked"]) == (10, 9)
    assert {name: stats["mean_rank"] for name, stats in result["variants"].items()} == order
    assert result["variants"]["B"] == {"mean_rank": 1, "first": 9, "last": 0, "ranked": 9}
    assert result["variants"]["A"]["last"] == 9 and result["variants"]["C-Opus"]["mean_rank"] == 3
    assert result["notes"] == [{"golden_id": first, "note": "W has an orphaned sentence", "labels": key["goldens"][first]}]


@pytest.mark.parametrize("ranking", ["V > W > X > Y", "V > W > X > Y > Y", "V > W > X > Y > Q", "the first one"])
def test_a_ranking_that_is_not_each_label_once_is_an_error_not_a_guess(ranking):
    text, key = blind.make_read(_blind_variants(), GOLDENS, seed=7)
    golden_id = sorted(key["goldens"])[0]

    with pytest.raises(blind.BlindError, match=golden_id):
        blind.score_read(text.replace(f"ranking[{golden_id}]: ", f"ranking[{golden_id}]: {ranking}"), key)


def test_rankings_accept_the_separators_people_type():
    assert blind.parse_ranking("x>w , z y", ["W", "X", "Y", "Z"]) == ["X", "W", "Z", "Y"]
    assert blind.parse_ranking("", ["W", "X"]) is None


def test_a_read_of_fewer_variants_uses_as_many_labels_and_ranks_among_them():
    four = [v for v in _blind_variants() if v["variant"] != "C-Opus"]

    text, key = blind.make_read(four, GOLDENS, seed=7)

    assert key["labels"] == ["V", "W", "X", "Y"] and "### Z" not in text
    golden_id, labels = next(iter(key["goldens"].items()))
    best_first = " > ".join(sorted(labels, key=lambda label: labels[label] != "C"))       # C first, the rest after
    result = blind.score_read(text.replace(f"ranking[{golden_id}]: ", f"ranking[{golden_id}]: {best_first}"), key)
    assert result["variants"]["C"]["first"] == 1 and result["ranked"] == 1
    with pytest.raises(blind.BlindError, match="2 to 5 variants"):
        blind.make_read(four[:1], GOLDENS, seed=7)


def _scores():
    """Every variant scored on every golden; A's g01..g03 are the three lowest."""
    def score(name, n):
        return 0.1 * n if (name == "A" and n <= 3) else 0.5 + 0.01 * n
    return {name: {(gid, "unsupported_specifics"): {"status": "ok", "score": score(name, n), "reason": f"why {name} {gid}"}
                   for n, gid in enumerate(GOLDENS, 1)} for name in VARIANTS}


def test_the_audit_takes_the_lowest_scores_first_then_a_seeded_sample():
    variants = _blind_variants(_scores())

    picked = blind.pick_findings(variants, seed=3)

    assert len(picked) == config.AUDIT_FINDINGS
    assert [(f["variant"], f["golden_id"]) for f in picked[:3]] == [("A", "g01"), ("A", "g02"), ("A", "g03")]
    assert [f["score"] for f in picked[:config.AUDIT_LOWEST]] == sorted(f["score"] for f in picked)[:config.AUDIT_LOWEST]
    assert picked == blind.pick_findings(variants, seed=3) != blind.pick_findings(variants, seed=4)
    assert len({(f["variant"], f["golden_id"]) for f in picked}) == config.AUDIT_FINDINGS


def test_audit_write_then_score_and_the_report_label(tmp_path):
    variants = _blind_variants(_scores())
    path = blind.write_audit(tmp_path, variants, seed=3)
    text = path.read_text()
    assert "why A g01" in text and "source text" in text and "profile" in text
    assert not any(f"variant {name}" in text for name in VARIANTS)
    for number in range(1, config.AUDIT_FINDINGS + 1):
        text = text.replace(f"verdict[F{number}]: ", f"verdict[F{number}]: {'wrong' if number <= 3 else 'correct'}")
    path.write_text(text)

    result = blind.score_audit(tmp_path)

    assert (result["of"], result["marked"], result["correct"]) == (10, 10, 7)
    assert json.loads((tmp_path / "audit.json").read_text())["correct"] == 7
    assert ablation.audit_label(result).startswith("UNRELIABLE")


def test_an_unknown_verdict_is_an_error(tmp_path):
    path = blind.write_audit(tmp_path, _blind_variants(_scores()), seed=3)
    path.write_text(path.read_text().replace("verdict[F1]: ", "verdict[F1]: mostly"))

    with pytest.raises(blind.BlindError, match="F1"):
        blind.score_audit(tmp_path)
