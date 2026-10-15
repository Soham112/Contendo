"""Phase 1 (latency experiment): the interleaved run order, the check that every
arm of a golden drafted from the same inputs, and the per-arm and per-golden
tables of ablation.md. Pure: no network, no eval environment."""

import ablation
import ablation_detail as detail
import eval_config as config

ARMS = list(config.PHASE1_PLAN.variants)
GOLDEN_IDS = list(config.PHASE1_PLAN.goldens)


def test_each_golden_runs_every_arm_once_in_a_seeded_order_that_varies_across_goldens():
    orders = detail.arm_orders(GOLDEN_IDS, ARMS, config.PHASE1_PLAN.seed)

    assert orders == detail.arm_orders(GOLDEN_IDS, ARMS, config.PHASE1_PLAN.seed)       # reproducible
    assert all(sorted(order) == sorted(ARMS) for order in orders.values())
    assert len({tuple(order) for order in orders.values()}) > 1                            # not one fixed order
    assert {order[0] for order in orders.values()} == set(ARMS)                            # every arm goes first somewhere


def test_runs_go_golden_by_golden():
    goldens = [{"id": golden_id} for golden_id in GOLDEN_IDS]
    orders = detail.arm_orders(GOLDEN_IDS, ARMS, 1)

    pairs = detail.interleaved_pairs(goldens, orders)

    assert [g["id"] for g, _ in pairs] == [golden_id for golden_id in GOLDEN_IDS for _ in ARMS]
    assert [variant for _, variant in pairs[:3]] == orders[GOLDEN_IDS[0]]


def _trace(chunks=(("c1", "pgvector is fast"),), block="<sources>S1</sources>", profile=None, target=150):
    return {"retrieved": [{"chunk_id": cid, "text": text, "similarity": 0.5} for cid, text in chunks],
            "profile_snapshot": profile or {"name": "Ana", "voice": "plain"},
            "retrieval_confidence": "high",
            "node_outputs": {"draft_frame_block": block, "length_target": {"max_words": target},
                             "perspective": "own", "coverage_gate": {"decision": "pass"},
                             "archetype_decision": {"allowed": ["general"]}}}


def test_input_fingerprints_match_for_the_same_inputs_and_name_the_part_that_differs():
    same = detail.input_fingerprints(_trace())
    assert same == detail.input_fingerprints(_trace())
    # Scores and the structure offer are not inputs to compare; chunk ids, text, order are.
    other_scores = _trace()
    other_scores["retrieved"][0]["similarity"] = 0.9
    assert detail.input_fingerprints(other_scores) == same

    changed = {
        "retrieved": _trace(chunks=(("c2", "pgvector is fast"),)),
        "sources_block": _trace(block="<sources>S2</sources>"),
        "profile": _trace(profile={"name": "Ana", "voice": "ornate"}),
        "plan": _trace(target=200),
    }
    for part, trace in changed.items():
        printed = detail.input_fingerprints(trace)
        assert [key for key in same if printed[key] != same[key]] == [part]


def _record(chosen, kept, reason=None, chosen_by=None, first_text_ms=4200.0, thinking=900, output=1300, checks=None):
    outputs = {"final_post": "One two three.", "length_target": None,
               "archetype_decision": {"archetype": kept, "chosen": chosen, "reason": reason,
                                      **({"chosen_by": chosen_by} if chosen_by else {})}}
    if checks is not None:
        outputs["checks_final"] = {"issues": [], "counts": checks}
    record = ablation.post_record(outputs, [], {"count_words": lambda t: len(t.split()),
                                                "prose_word_count": lambda t: len(t.split())})
    record["draft"] = {"model": "claude-opus-5-5", "output_tokens": output, "thinking_tokens": thinking,
                       "first_text_ms": first_text_ms, "marked_words": 3, "tokens_per_word": 1.0, "stop_reason": "end_turn"}
    return record


def _row(golden_id, record, seconds, position, inputs):
    return {"golden_id": golden_id, "status": "ok", "seconds": seconds, "arm_position": position,
            "inputs": inputs, "record": record,
            "pipeline": {"calls": 1, "input_tokens": 1, "output_tokens": 1, "thinking_tokens": 0, "cost_usd": 0.01,
                         "by_model": {}}}


def _variant(name, rows):
    return {"meta": {"variant": name, "run_id": f"run-{name}", "git": {}}, "runs": rows, "scores": {}, "instrument": []}


def test_the_report_gives_speed_tokens_structures_fallbacks_and_inputs_per_golden():
    same = {"retrieved": "a", "sources_block": "b", "profile": "c", "plan": "d"}
    c_rows = [_row("g1", _record("teach_me_something", "teach_me_something", first_text_ms=11000.0), 21.0, 2, same),
              _row("g2", _record("personal_story", "general", reason="the drafter found no event that fits the topic"),
                   19.5, 1, same)]
    d_rows = [_row("g1", _record("made_up", "general", reason="not an allowed type for these sources",
                                 chosen_by="drafter", first_text_ms=3000.0, thinking=200), 9.0, 1, same),
              _row("g2", _record("contrarian_take", "contrarian_take", chosen_by="drafter"), 8.5, 2,
                   {**same, "retrieved": "zzz"})]

    report = "\n".join(detail.detail_lines([_variant("C-Opus", c_rows), _variant("D-Opus", d_rows)]))

    assert "| C-Opus | 2 | 4.2 / 11.0 | 900 / 900 | 1300 / 1300 |" in report
    assert "| D-Opus | 2 | 3.0 / 4.2 | 200 / 900 | 1300 / 1300 |" in report
    assert "| C-Opus | small_model | 2 | 0 | the drafter found no event that fits the topic 1 |" in report
    assert "| D-Opus | drafter | 2 | 1 | – |" in report
    assert "| g1 | 21.0 s (#2) | 9.0 s (#1) | same |" in report
    assert "| g2 | 19.5 s (#1) | 8.5 s (#2) | DIFFERS: retrieved |" in report
    assert "| g1 | teach_me_something | made_up → general |" in report
    assert "| g2 | personal_story → general | contrarian_take |" in report


def test_the_phase1_rules_are_the_ones_fixed_before_the_run():
    rules = config.PHASE1_PLAN.rules
    assert "at least 15% lower" in rules[1] and "p95 wall time is not higher" in rules[1]
    assert "lowest p50" in rules[1] and "7 or more of the 10 goldens" in rules[2]
    assert config.PHASE1_SPEED_MARGIN == 0.15 and config.PHASE1_CLEARLY_SHARE == 0.7
    assert any("golden by golden" in note and "same inputs" in note for note in config.PHASE1_PLAN.notes)
