"""Where a generation's time goes: every run's trace records the wall time of
each graph step (step_timings), of each part of retrieval (retrieval_timings)
and of the whole run (run_seconds). Recording it makes no model call."""
import pytest

from tests.test_generation_trace import STANDARD_RUN, USER, _only_trace, _run, seeded_kb  # noqa: F401

SHARED = ["load_profile", "retrieval", "plan"]
RETRIEVAL_PARTS = ["experience_nodes", "hybrid_search", "entity_enrichment", "source_context", "retrieval_stats"]


def _steps(outputs: dict) -> list[str]:
    return [t["step"] for t in outputs["step_timings"]]


@pytest.mark.parametrize("variant", ["C", "C-Opus"])
def test_a_single_writer_run_times_every_step_and_the_whole_run(claude, fake_db, seeded_kb, variant):
    from pipeline.graph import run_pipeline
    from tests.conftest import ARCHETYPE_GENERAL
    from tests.generation_fixtures import enveloped

    claude.queue(ARCHETYPE_GENERAL, enveloped("pgvector makes retrieval fast. [[R]]"))
    run_pipeline("pgvector retrieval", "linkedin post", "casual", user_id=USER, variant=variant)

    outputs = _only_trace(fake_db)["node_outputs"]
    assert _steps(outputs) == [*SHARED, "structure", "draft", "strip", "finalise", "checks"]
    assert [t["step"] for t in outputs["retrieval_timings"]] == RETRIEVAL_PARTS
    for timing in [*outputs["step_timings"], *outputs["retrieval_timings"]]:
        assert isinstance(timing["seconds"], float) and timing["seconds"] >= 0
    # The run covers every step in it, and retrieval covers its parts.
    assert outputs["run_seconds"] >= sum(t["seconds"] for t in outputs["step_timings"]) - 0.01
    [retrieval] = [t for t in outputs["step_timings"] if t["step"] == "retrieval"]
    assert retrieval["seconds"] >= sum(t["seconds"] for t in outputs["retrieval_timings"]) - 0.01
    assert len(claude.calls) == 2                      # timing adds no call


def test_a_run_the_coverage_gate_stops_is_timed_up_to_the_gate(claude, fake_db, seeded_kb):
    from pipeline.graph import run_pipeline

    result = run_pipeline("Medieval falconry techniques for hunting hares", "linkedin post", "casual",
                          user_id=USER, variant="C-Opus")

    assert result["status"] == "low_coverage" and claude.calls == []
    outputs = _only_trace(fake_db)["node_outputs"]
    assert _steps(outputs) == ["load_profile", "retrieval"]
    assert outputs["run_seconds"] >= 0


def test_pipeline_a_times_the_shared_steps(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)
    _run()

    outputs = _only_trace(fake_db)["node_outputs"]
    assert _steps(outputs) == SHARED                   # A's own rewrite chain is not timed
    assert "run_seconds" in outputs and outputs["retrieval_timings"]


def test_the_trace_records_each_calls_speed_settings_and_start(claude, fake_db, seeded_kb):
    from pipeline.graph import run_pipeline
    from tests.conftest import ARCHETYPE_GENERAL
    from tests.generation_fixtures import enveloped

    claude.queue(ARCHETYPE_GENERAL, enveloped("pgvector makes retrieval fast. [[R]]"))
    run_pipeline("pgvector retrieval", "linkedin post", "casual", user_id=USER, variant="C-Opus")

    structure, draft = _only_trace(fake_db)["llm_calls"]
    assert (structure["event_type"], draft["event_type"]) == ("archetype", "generate")
    assert draft["effort"] == "medium" and draft["thinking"] is None      # Opus 5.5 drafts at medium, thinking by default
    assert structure["effort"] is None
    assert 0 <= structure["started_ms"] <= draft["started_ms"]           # structure, then draft
