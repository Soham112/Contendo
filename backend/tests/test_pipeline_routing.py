"""LangGraph routing in pipeline/graph.py.

The agent nodes are replaced with stubs, so these tests check only which nodes
run and in what order: no Claude calls, no retrieval.
"""

import pytest


@pytest.fixture
def run_graph(monkeypatch):
    import pipeline.graph as graph

    def factory(scores):
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

        compiled = graph.build_graph()

        def run(quality):
            result = compiled.invoke({"topic": "t", "quality": quality, "user_id": "u"})
            return visited, result

        return run

    return factory


@pytest.mark.parametrize("quality", ["draft", "standard"])
def test_non_polished_runs_each_node_once_and_never_scores(run_graph, quality):
    visited, result = run_graph(scores=[])(quality)

    assert visited == [
        "load_profile", "retrieval", "draft", "critic", "humanizer",
        "predictability_audit", "word_count_enforcer",
    ]
    assert result["final_post"] == "draft text"


def test_polished_stops_after_first_score_when_it_passes(run_graph):
    visited, _ = run_graph(scores=[90])("polished")

    assert visited.count("humanizer") == 1
    assert visited.count("scorer") == 1
    assert visited[-1] == "word_count_enforcer"


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
