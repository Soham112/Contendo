"""Judge a run's generations with DeepEval metrics. Results are cached.

From the evals folder, with the backend venv:
    python judge.py <run_id>                                  # default judge (eval_config.JUDGE_MODEL)
    python judge.py <run_id> --judge-model SONNET --only pm-07 --only ds-07

Each judge model writes its own scores file (eval_config.SCORES_FILES). Reads results/<run_id>/runs.jsonl, loads each trace from generation_traces, and
appends one line per (golden, metric) to results/<run_id>/scores.jsonl. A
(golden, trace, metric, judge model) that already has an ok or skipped line is
not judged again; errors are retried on the next run. Billing and auth errors
stop the run at once: every later call would fail the same way.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import json
import sys
from typing import Any

import eval_config as config
import spend
from guard import EnvGuardError
from loaders import FixtureError, load_goldens, load_persona, load_users, persona_slugs
from reporting import read_jsonl


def cache_key(row: dict[str, Any]) -> tuple:
    return (row["golden_id"], row["trace_id"], row["metric"], row["judge_model"])


def judge_cost(calls: list[dict[str, Any]]) -> dict[str, Any]:
    from llm.pricing import call_cost

    tokens_in = sum(c["input_tokens"] for c in calls)
    tokens_out = sum(c["output_tokens"] for c in calls)
    cost = sum(call_cost(c["model"], c["input_tokens"], c["output_tokens"]) for c in calls)
    return {"judge_calls": len(calls), "input_tokens": tokens_in, "output_tokens": tokens_out, "cost_usd": round(cost, 6)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id")
    parser.add_argument("--judge-model", choices=sorted(config.SCORES_FILES), default=config.JUDGE_MODEL)
    parser.add_argument("--only", action="append", help="golden id (repeatable); default: every ok run")
    parser.add_argument("--metric", action="append", choices=list(config.METRIC_ORDER),
                        help="judge only this metric (repeatable); default: all")
    spend.add_arguments(parser)
    args = parser.parse_args(argv)

    run_dir = config.RESULTS_DIR / args.run_id
    runs = read_jsonl(run_dir / "runs.jsonl")
    if not runs:
        print(f"no runs.jsonl in {run_dir}", file=sys.stderr)
        return 2
    if args.only:
        unknown = sorted(set(args.only) - {r["golden_id"] for r in runs})
        if unknown:
            print(f"golden id(s) not in this run: {unknown}", file=sys.stderr)
            return 2
        runs = [r for r in runs if r["golden_id"] in args.only]
    try:
        users = load_users()
        personas = {s: load_persona(s) for s in persona_slugs()}
        goldens = {g["id"]: g for g in load_goldens(personas=personas)}
        env.verify_anthropic_key()
        client = env.backend_client()
    except (EnvGuardError, FixtureError) as exc:
        print(f"refusing to judge: {exc}", file=sys.stderr)
        return 2

    from llm.client import trace_calls
    from llm.pricing import call_cost

    import metrics
    from judge_model import ContendoJudge, is_fatal_api_error

    cap = spend.open_cap(args.ablation, args.spend_cap, call_cost)
    scores_path = run_dir / config.SCORES_FILES[args.judge_model]
    print(f"Judge: {args.judge_model} -> {scores_path.name}")
    done = {cache_key(r) for r in read_jsonl(scores_path) if r["status"] in ("ok", "skipped")}
    specs = [s for s in metrics.judge_metric_specs() if not args.metric or s.name in args.metric]
    want_recall = not args.metric or "source_recall" in args.metric

    with scores_path.open("a") as out:
        def write(row: dict[str, Any]) -> None:
            out.write(json.dumps(row) + "\n")
            out.flush()
            score = "-" if row.get("score") is None else f"{row['score']:.2f}"
            print(f"  {row['golden_id']:<12} {row['metric']:<22} {row['status']:<8} {score}")

        for run in cap.guard(runs, lambda run, done: f"judge {args.judge_model} on run {args.run_id} before "
                                                     f"{run['golden_id']}: {done} of {len(runs)} posts looked at"):
            if run.get("status") != "ok":
                print(f"  {run['golden_id']:<12} not judged: run status {run.get('status')}")
                continue
            golden = goldens[run["golden_id"]]
            user_id = users[golden["persona"]]
            base = {
                "golden_id": golden["id"], "trace_id": run["trace_id"], "persona": golden["persona"],
                "difficulty": golden["difficulty"], "judge_model": args.judge_model,
            }
            pending = [s.name for s in specs] + (["source_recall"] if want_recall else [])
            if all(cache_key({**base, "metric": m}) in done for m in pending):
                print(f"  {golden['id']:<12} cached")
                continue

            trace = (client.table("generation_traces").select("*")
                     .eq("id", run["trace_id"]).eq("user_id", user_id).execute().data or [None])[0]
            if trace is None:
                print(f"  {golden['id']:<12} trace {run['trace_id']} not found", file=sys.stderr)
                continue
            cases = metrics.build_cases(trace, golden)

            # Deterministic metric: no judge calls.
            if want_recall and cache_key({**base, "metric": "source_recall"}) not in done:
                recall = metrics.SourceRecallMetric(golden["expected_source_titles"])
                recall.measure(cases["chunks"], retrieved=metrics.retrieved_titles(trace))
                write({**base, "metric": "source_recall", "status": "skipped" if recall.skipped else "ok",
                       "score": recall.score, "threshold": recall.threshold, "success": recall.success,
                       "reason": recall.reason, "judge_calls": 0, "input_tokens": 0, "output_tokens": 0,
                       "cost_usd": 0.0})

            for spec in specs:
                row = {**base, "metric": spec.name, "threshold": config.THRESHOLDS[spec.name]}
                if cache_key(row) in done:
                    continue
                case = cases[spec.case]
                if spec.needs_chunks and not metrics.chunk_texts(trace):
                    write({**row, "status": "skipped", "score": None, "success": None,
                           "reason": "skipped: retrieval returned no chunks", "judge_calls": 0,
                           "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
                    continue
                judge = ContendoJudge(user_id=user_id, model_constant=args.judge_model)
                metric = spec.build(judge)
                with trace_calls() as calls:
                    try:
                        metric.measure(case, _show_indicator=False)
                        status, error = "ok", None
                    except Exception as exc:
                        status, error = "error", f"{type(exc).__name__}: {exc}"
                        fatal = is_fatal_api_error(exc)
                write({**row, "status": status, "score": metric.score if status == "ok" else None,
                       "success": metric.success if status == "ok" else None,
                       "reason": metric.reason if status == "ok" else error,
                       "schema_paths": dict(judge.stats), **judge_cost(calls)})
                cap.record(calls, f"judge {args.judge_model} {spec.name} {args.run_id} {golden['id']}")
                if status == "error" and fatal:
                    print(f"Stopping: {error}\nFix this (e.g. add credits), then re-run; finished results are cached.",
                          file=sys.stderr)
                    return 3

    print(f"Scores: {scores_path}. Next: python report.py {args.run_id}")
    return spend.STOPPED_EXIT if cap.stopped_at else 0


if __name__ == "__main__":
    sys.exit(main())
