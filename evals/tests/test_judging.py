"""Judge adapter, metrics and report. Fake complete(), no network, no backend imports."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import guard

deepeval = pytest.importorskip("deepeval")

import metrics  # noqa: E402
import reporting as report  # noqa: E402
from judge_model import ContendoJudge  # noqa: E402


class Verdict(BaseModel):
    verdict: str
    reason: str


class FakeComplete:
    """Stands in for llm.client.complete: returns queued messages and records kwargs."""

    def __init__(self, *messages):
        self.messages = list(messages)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.messages.pop(0)


def tool_message(data):
    return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=data)])


def text_message(text):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def make_judge(fake):
    return ContendoJudge(user_id="11111111-1111-4111-8111-111111111111", complete_fn=fake, model_id="judge-model-id")


# --- judge adapter ----------------------------------------------------------

def test_schema_answer_comes_from_a_forced_tool_call():
    fake = FakeComplete(tool_message({"verdict": "yes", "reason": "supported"}))
    judge = make_judge(fake)
    result = judge.generate("is it supported?", schema=Verdict)
    assert result == Verdict(verdict="yes", reason="supported")
    call = fake.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "submit_answer"}
    assert call["tools"][0]["input_schema"] == Verdict.model_json_schema()
    assert call["event_type"] == "eval_judge"
    assert call["user_id"] == "11111111-1111-4111-8111-111111111111"
    assert judge.stats == {"tool": 1, "text_fallback": 0, "plain": 0}


def test_invalid_tool_input_falls_back_to_json_text():
    fake = FakeComplete(
        tool_message({"verdict": "yes"}),  # missing reason
        text_message('```json\n{"verdict": "no", "reason": "not in context"}\n```'),
    )
    judge = make_judge(fake)
    assert judge.generate("q", schema=Verdict) == Verdict(verdict="no", reason="not in context")
    assert "tools" not in fake.calls[1]
    assert judge.stats["text_fallback"] == 1


def test_plain_generation_returns_text():
    judge = make_judge(FakeComplete(text_message("hello")))
    assert judge.generate("say hello") == "hello"


# --- metrics ----------------------------------------------------------------

TRACE = {
    "retrieved": [
        {"source_title": "A", "text": "chunk a"},
        {"source_title": "B", "text": "chunk b"},
        {"source_title": "B", "text": "  "},
    ],
    "node_outputs": {"final_post": "the post"},
    "profile_snapshot": {"name": "N"},
}
GOLDEN = {"id": "x-01", "topic": "Topic", "context": "Some context", "expected_source_titles": ["A", "C"]}


def test_cases_use_chunks_and_add_profile_only_to_grounded_case():
    cases = metrics.build_cases(TRACE, GOLDEN, profile_formatter=lambda p: f"PROFILE {p['name']}")
    assert cases["chunks"].input == "Topic\n\nContext: Some context"
    assert cases["chunks"].actual_output == "the post"
    assert cases["chunks"].retrieval_context == ["chunk a", "chunk b"]
    assert cases["grounded"].retrieval_context == ["chunk a", "chunk b", "PROFILE N"]


def test_source_recall_is_share_of_expected_titles():
    m = metrics.SourceRecallMetric(["A", "C"], threshold=0.5)
    assert m.measure(None, retrieved=metrics.retrieved_titles(TRACE)) == 0.5
    assert m.success is True
    assert "missing: ['C']" in m.reason


def test_source_recall_is_skipped_not_zero_without_expected_sources():
    m = metrics.SourceRecallMetric([])
    assert m.measure(None, retrieved=["A"]) is None
    assert m.skipped and m.score is None and m.success is None


# --- report -----------------------------------------------------------------

def _score(gid, metric, score, success, status="ok", **extra):
    return {"golden_id": gid, "metric": metric, "score": score, "success": success, "status": status,
            "judge_model": "HAIKU", "persona": "ds", "difficulty": "rich", "reason": f"{metric} reason", **extra}


def test_report_excludes_skipped_from_means_and_counts_costs():
    meta = {"run_id": "r1", "quality": "standard", "project_ref": "ref", "git": {"commit": "abc", "dirty": False}}
    runs = [{"golden_id": "g1", "status": "ok", "pipeline": {"calls": 7, "cost_usd": 0.05}},
            {"golden_id": "g2", "status": "no_trace"}]
    scores = [
        _score("g1", "faithfulness", 0.9, True, judge_calls=4, cost_usd=0.01, schema_paths={"tool": 4}),
        _score("g1", "source_recall", None, None, status="skipped"),
        _score("g1", "faithfulness", 0.4, False, judge_model="SONNET"),  # other judge model: ignored
    ]
    text = report.build_report(meta, runs, scores, {"g1": {"topic": "T"}}, judge_model="HAIKU")
    assert "| faithfulness | 1 | 0.90 | 100% |" in text
    assert "| source_recall | 0 | – | – | 0.5 | 1 | 0 |" in text
    assert "1 skipped (no trace)" in text
    assert "**$0.0600**" in text


# --- module names -----------------------------------------------------------

def test_no_evals_module_shadows_a_backend_package():
    backend_names = {p.stem for p in guard.BACKEND_DIR.iterdir()
                     if (p.is_dir() and p.name not in {"venv", "__pycache__", "data", "migrations"}) or p.suffix == ".py"}
    evals_names = {p.stem for p in guard.EVALS_DIR.glob("*.py")}
    assert not (backend_names & evals_names), backend_names & evals_names


def test_tests_never_bootstrap_the_real_env():
    import sys
    assert "env" not in sys.modules, "a test imported env.py, which reads the real evals/.env"


# --- fatal errors and judge comparison --------------------------------------

def _api_error(cls, message, status):
    import anthropic
    import httpx
    response = httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return cls(message, response=response, body=None)


def test_credit_and_auth_errors_are_fatal_other_errors_are_not():
    import anthropic
    from judge_model import is_fatal_api_error
    assert is_fatal_api_error(_api_error(anthropic.BadRequestError, "Your credit balance is too low", 400))
    assert is_fatal_api_error(_api_error(anthropic.AuthenticationError, "invalid x-api-key", 401))
    assert not is_fatal_api_error(_api_error(anthropic.BadRequestError, "prompt is too long", 400))
    assert not is_fatal_api_error(ValueError("bad json"))


def test_comparison_uses_only_pairs_both_judges_scored():
    a = [_score("g1", "faithfulness", 0.9, True), _score("g2", "faithfulness", 0.8, True),
         _score("g1", "answer_relevancy", 0.2, False)]
    b = [_score("g1", "faithfulness", 0.5, False, judge_model="SONNET"),
         _score("g1", "answer_relevancy", 0.9, True, judge_model="SONNET", status="error")]
    text = report.build_judge_comparison(a, b, "HAIKU", "SONNET", "r1")
    assert "| faithfulness | 1 | 0.90 | 0.50 | 100% | 0% | g1 |" in text
    assert "answer_relevancy" not in text.split("## Per golden")[0].split("|---|")[1]
    assert "0.90 / 0.50 ⚠" in text
