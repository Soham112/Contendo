"""The ablation's spend cap, with a fake model: the sum is measured cost at the
backend's list prices, a script stops before the next post once the cap is
reached, and the ledger carries over to the next script."""

import json

import pytest

import eval_config as config
import spend

HAIKU = "claude-haiku-4-5-20251001"


class FakeModel:
    """Stands in for the pipeline: each post it 'writes' is one call of a known
    size, recorded as llm.client's trace records a call."""

    def __init__(self, output_tokens: int = 1_000_000):      # one million Haiku 4.5 output tokens: $5 a post
        self.output_tokens, self.posts = output_tokens, []

    def write(self, post: str) -> list[dict]:
        self.posts.append(post)
        return [{"event_type": "generate", "model": HAIKU, "input_tokens": 0, "output_tokens": self.output_tokens}]


def _run_script(cap, model, posts, script="run"):
    """The loop every script has: guard the posts, do one, record what it cost."""
    for post in cap.guard(posts, lambda post, done: f"{script} before {post}: {done} of {len(posts)} done"):
        cap.record(model.write(post), f"{script} {post}")


@pytest.fixture
def call_cost(backend):
    from llm.pricing import call_cost

    return call_cost


def test_the_default_cap_is_fourteen_dollars():
    assert config.EVAL_SPEND_CAP_USD == 14.0


def test_a_run_stops_before_the_next_post_once_the_cap_is_reached(tmp_path, call_cost, capsys):
    ledger = tmp_path / "full" / spend.LEDGER_FILE
    cap, model = spend.SpendCap(ledger, 14.0, call_cost), FakeModel()

    _run_script(cap, model, ["p1", "p2", "p3", "p4", "p5"])

    assert model.posts == ["p1", "p2", "p3"]              # $5, $10, $15: the third crosses the cap and is finished
    assert cap.spent_usd == pytest.approx(15.0) and cap.reached
    assert cap.stopped_at == "run before p4: 3 of 5 done"
    said = capsys.readouterr().out
    assert "SPEND CAP REACHED: $15.00 measured against a cap of $14.00" in said and "run before p4: 3 of 5 done" in said
    written = json.loads(ledger.read_text())
    assert (written["cap_usd"], written["spent_usd"], written["reached"]) == (14.0, 15.0, True)
    assert [(e["item"], e["cost_usd"], e["calls"]) for e in written["entries"]] == [
        ("run p1", 5.0, 1), ("run p2", 5.0, 1), ("run p3", 5.0, 1)]
    assert written["stops"] == ["run before p4: 3 of 5 done"]


def test_the_next_script_of_the_same_ablation_starts_from_the_ledger(tmp_path, call_cost):
    ledger = tmp_path / "full" / spend.LEDGER_FILE
    _run_script(spend.SpendCap(ledger, 14.0, call_cost), FakeModel(), ["p1", "p2"])          # $10 by the pipeline runs

    judge_cap, judge = spend.SpendCap(ledger, 14.0, call_cost), FakeModel(output_tokens=500_000)   # $2.50 a post
    _run_script(judge_cap, judge, ["p1", "p2", "p3"], script="judge")

    assert judge_cap.spent_usd == pytest.approx(15.0)
    assert judge.posts == ["p1", "p2"] and judge_cap.stopped_at == "judge before p3: 2 of 3 done"

    after, late = spend.SpendCap(ledger, 14.0, call_cost), FakeModel()
    _run_script(after, late, ["p1"], script="regression")
    assert late.posts == [] and after.stopped_at == "regression before p1: 0 of 1 done"
    assert json.loads(ledger.read_text())["stops"] == ["judge before p3: 2 of 3 done", "regression before p1: 0 of 1 done"]


def test_under_the_cap_everything_runs_and_nothing_is_marked_stopped(tmp_path, call_cost):
    cap, model = spend.SpendCap(tmp_path / spend.LEDGER_FILE, 14.0, call_cost), FakeModel(output_tokens=100_000)

    _run_script(cap, model, ["p1", "p2", "p3"])

    assert model.posts == ["p1", "p2", "p3"] and cap.spent_usd == pytest.approx(1.5)
    assert not cap.reached and cap.stopped_at is None


def test_a_call_to_a_model_with_no_price_is_an_error_not_a_free_call(tmp_path, call_cost):
    cap = spend.SpendCap(tmp_path / spend.LEDGER_FILE, 14.0, call_cost)

    with pytest.raises(KeyError):
        cap.record([{"model": "claude-some-other-model", "input_tokens": 1, "output_tokens": 1}], "run p1")


def test_outside_an_ablation_nothing_is_capped_or_written(tmp_path, call_cost, monkeypatch):
    monkeypatch.setattr(config, "ABLATIONS_DIR", tmp_path)
    cap, model = spend.open_cap(None, 14.0, call_cost), FakeModel()

    _run_script(cap, model, ["p1", "p2", "p3", "p4"])

    assert model.posts == ["p1", "p2", "p3", "p4"] and cap.stopped_at is None and list(tmp_path.iterdir()) == []
    named = spend.open_cap("full", 14.0, call_cost)
    assert isinstance(named, spend.SpendCap) and named.ledger == tmp_path / "full" / spend.LEDGER_FILE


def test_every_script_of_the_ablation_takes_the_cap():
    for script in ("run.py", "judge.py", "review_regression.py"):
        source = (config.EVALS_DIR / script).read_text()
        assert "spend.add_arguments(parser)" in source and "cap.guard(" in source and "cap.record(" in source, script
