"""LangGraph routing in pipeline/graph.py, and which pipeline variant runs.

The agent nodes are replaced with stubs, so these tests check only which nodes
run and in what order: no Claude calls, no retrieval.
"""

import pytest

A_NODE_ORDER = [
    "load_profile", "retrieval", "draft", "critic", "humanizer",
    "predictability_audit", "word_count_enforcer", "fact_checker",
]
# B and C are the same for now (see _wire_cited_draft in pipeline/graph.py):
# structure → cited draft → strip → finalise, then trim → finalise only when the
# post is over its maximum. Checks, review and redraft for B are added later.
SINGLE_WRITER_NODE_ORDER = ["load_profile", "retrieval", "structure", "cited_draft", "strip", "finalise"]


@pytest.fixture
def stub_nodes(monkeypatch):
    """Replace every agent node with a stub. stub_nodes(scores) returns the list
    the stubs append their names to, in the order they run."""
    import pipeline.graph as graph

    def install(scores, finalise_length="ok"):
        visited: list[str] = []
        score_iter = iter(scores)

        def stub(name, fn=None):
            def node(state):
                visited.append(name)
                if fn:
                    fn(state)
                return state
            return node

        def humanize(state):
            state["iterations"] = state.get("iterations", 0) + 1  # as the real node does

        def score(state):
            state["score"] = next(score_iter)

        def draft(state):
            state["current_draft"] = "draft text"

        monkeypatch.setattr(graph, "load_profile_node", stub("load_profile", lambda s: s.update(iterations=0)))
        monkeypatch.setattr(graph, "retrieval_node", stub("retrieval"))
        monkeypatch.setattr(graph, "draft_node", stub("draft", draft))
        monkeypatch.setattr(graph, "critic_node", stub("critic"))
        monkeypatch.setattr(graph, "humanizer_node", stub("humanizer", humanize))
        monkeypatch.setattr(graph, "predictability_audit_node", stub("predictability_audit"))
        monkeypatch.setattr(graph, "scorer_node", stub("scorer", score))
        monkeypatch.setattr(graph, "word_count_enforcer_node", stub("word_count_enforcer"))
        monkeypatch.setattr(graph, "fact_check_node", stub("fact_checker"))
        monkeypatch.setattr(graph, "structure_node", stub("structure"))
        monkeypatch.setattr(graph, "cited_draft_node", stub("cited_draft", draft))
        monkeypatch.setattr(graph, "strip_draft_node", stub("strip"))
        monkeypatch.setattr(graph, "finalise_draft_node", stub("finalise", lambda s: s.update(
            final_post=s["current_draft"], final_validation={"length": finalise_length})))
        monkeypatch.setattr(graph, "trim_node", stub("trim"))
        monkeypatch.setattr(graph, "finalise_trimmed_node", stub("finalise_trimmed"))
        monkeypatch.setattr(graph, "truncated_node", stub("truncated", lambda s: s.update(final_post="")))
        return visited

    return install


@pytest.fixture
def run_graph(stub_nodes):
    import pipeline.graph as graph

    def factory(scores, variant="A", finalise_length="ok"):
        visited = stub_nodes(scores, finalise_length)
        compiled = graph.build_graph(variant)

        def run(quality, **state):
            result = compiled.invoke({"topic": "t", "quality": quality, "user_id": "u", **state})
            return visited, result

        return run

    return factory


@pytest.mark.parametrize("quality", ["draft", "standard"])
def test_non_polished_runs_each_node_once_and_never_scores(run_graph, quality):
    visited, result = run_graph(scores=[])(quality)

    assert visited == A_NODE_ORDER
    assert result["final_post"] == "draft text"


def test_polished_stops_after_first_score_when_it_passes(run_graph):
    visited, _ = run_graph(scores=[90])("polished")

    assert visited.count("humanizer") == 1
    assert visited.count("scorer") == 1
    assert visited[-2:] == ["word_count_enforcer", "fact_checker"]


def test_polished_retries_until_score_passes(run_graph):
    visited, result = run_graph(scores=[60, 80])("polished")

    assert visited.count("humanizer") == 2
    assert visited.count("scorer") == 2
    assert result["score"] == 80


def test_polished_stops_after_three_rewrites_even_if_score_stays_low(run_graph):
    visited, result = run_graph(scores=[10, 10, 10, 10, 10])("polished")

    assert visited.count("humanizer") == 3
    assert visited.count("scorer") == 3
    assert visited.count("word_count_enforcer") == 1
    assert result["iterations"] == 3


def test_word_count_enforcer_runs_after_scoring_not_inside_the_loop(run_graph):
    visited, _ = run_graph(scores=[50, 50, 50])("polished")

    last_scorer = max(i for i, n in enumerate(visited) if n == "scorer")
    assert visited.index("word_count_enforcer") > last_scorer


def test_fact_check_runs_last_after_the_enforcer_in_every_quality(run_graph):
    for quality in ("draft", "standard", "polished"):
        visited, _ = run_graph(scores=[90])(quality)
        assert visited[-1] == "fact_checker", quality
        assert visited[-2] == "word_count_enforcer", quality


# --- Pipeline variant ---------------------------------------------------------

@pytest.fixture
def stubbed_pipelines(stub_nodes, monkeypatch):
    """run_pipeline's compiled graphs rebuilt over stubbed nodes; returns the visited list."""
    import pipeline.graph as graph
    from config import features

    visited = stub_nodes([])
    monkeypatch.setattr(graph, "PIPELINES", {v: graph.build_graph(v) for v in features.PIPELINE_VARIANTS})
    return visited


def _recorded_variant(fake_db) -> str:
    [trace] = fake_db.tables["generation_traces"]
    return trace["node_outputs"]["variant"]


def _run_pipeline(**kwargs):
    from pipeline.graph import run_pipeline

    return run_pipeline(topic="t", format="linkedin post", tone="casual", user_id="u", **kwargs)


def test_the_default_variant_is_a(monkeypatch):
    from config import features

    monkeypatch.delenv("PIPELINE_VARIANT", raising=False)
    assert features.pipeline_variant() == "A"
    monkeypatch.setenv("PIPELINE_VARIANT", "")
    assert features.pipeline_variant() == "A"


@pytest.mark.parametrize("variant", ["A", "B", "C"])
def test_the_environment_variable_selects_the_variant(monkeypatch, variant):
    from config import features

    monkeypatch.setenv("PIPELINE_VARIANT", f" {variant} ")
    assert features.pipeline_variant() == variant


@pytest.mark.parametrize("value", ["D", "b", "single-writer", "A,B"])
def test_an_unknown_variant_in_the_environment_is_an_error(monkeypatch, value):
    from config import features

    monkeypatch.setenv("PIPELINE_VARIANT", value)
    with pytest.raises(features.PipelineConfigError):
        features.pipeline_variant()


def test_the_server_refuses_to_start_with_an_unknown_variant(monkeypatch):
    from fastapi.testclient import TestClient

    from config import features
    from main import app

    monkeypatch.setenv("PIPELINE_VARIANT", "D")
    with pytest.raises(features.PipelineConfigError):
        with TestClient(app):
            pass


def test_build_graph_rejects_an_unknown_variant():
    import pipeline.graph as graph
    from config import features

    with pytest.raises(features.PipelineConfigError):
        graph.build_graph("D")


def test_every_variant_has_a_compiled_pipeline():
    import pipeline.graph as graph
    from config import features

    assert set(graph.PIPELINES) == set(features.PIPELINE_VARIANTS)


def test_variant_a_runs_the_rewrite_chain(run_graph):
    visited, result = run_graph(scores=[], variant="A")("standard")

    assert visited == A_NODE_ORDER
    assert result["final_post"] == "draft text"


@pytest.mark.parametrize("variant", ["B", "C"])
@pytest.mark.parametrize("quality", ["draft", "standard", "polished"])
def test_single_writer_variants_run_one_draft_and_no_rewriting_node(run_graph, variant, quality):
    visited, result = run_graph(scores=[], variant=variant)(quality)

    assert visited == SINGLE_WRITER_NODE_ORDER
    assert result["final_post"] == "draft text"


@pytest.mark.parametrize("variant", ["B", "C"])
def test_an_over_length_post_goes_through_trim_and_is_finalised_again(run_graph, variant):
    visited, _ = run_graph(scores=[], variant=variant, finalise_length="over_length")("standard")

    assert visited == [*SINGLE_WRITER_NODE_ORDER, "trim", "finalise_trimmed"]


@pytest.mark.parametrize("variant", ["B", "C"])
@pytest.mark.parametrize("length", ["ok", "under_length", "no_target"])
def test_a_post_that_is_not_over_length_is_never_trimmed(run_graph, variant, length):
    visited, _ = run_graph(scores=[], variant=variant, finalise_length=length)("standard")

    assert visited == SINGLE_WRITER_NODE_ORDER


@pytest.mark.parametrize("variant", ["B", "C"])
def test_a_truncated_draft_skips_every_later_step(run_graph, variant):
    visited, result = run_graph(scores=[], variant=variant)("standard", draft_truncated={"max_tokens": 2000})

    assert visited == ["load_profile", "retrieval", "structure", "cited_draft", "truncated"]
    assert result["final_post"] == ""


def test_run_pipeline_defaults_to_a_and_records_it_in_the_trace(stubbed_pipelines, fake_db):
    _run_pipeline()

    assert _recorded_variant(fake_db) == "A"
    assert stubbed_pipelines == A_NODE_ORDER


def test_run_pipeline_uses_the_configured_variant(stubbed_pipelines, fake_db, monkeypatch):
    monkeypatch.setenv("PIPELINE_VARIANT", "B")
    _run_pipeline()

    assert _recorded_variant(fake_db) == "B"
    assert stubbed_pipelines == SINGLE_WRITER_NODE_ORDER


def test_an_explicit_variant_overrides_the_configured_one(stubbed_pipelines, fake_db, monkeypatch):
    monkeypatch.setenv("PIPELINE_VARIANT", "B")
    _run_pipeline(variant="C")

    assert _recorded_variant(fake_db) == "C"


def test_run_pipeline_rejects_an_unknown_variant_before_running_anything(stubbed_pipelines, fake_db):
    from config import features

    with pytest.raises(features.PipelineConfigError):
        _run_pipeline(variant="D")
    assert stubbed_pipelines == []
    assert fake_db.tables.get("generation_traces", []) == []


def test_a_generate_request_cannot_choose_the_variant(stubbed_pipelines, fake_db, client, auth_headers):
    resp = client.post(
        "/generate",
        json={"topic": "t", "format": "linkedin post", "tone": "casual", "variant": "B"},
        headers=auth_headers("u"),
    )

    assert resp.status_code == 200
    assert _recorded_variant(fake_db) == "A"
