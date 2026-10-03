"""Run goldens through the real pipeline as their persona.

From the evals folder, with the backend venv:
    python run.py --quality standard --only pm-01     # one golden
    python run.py --quality standard                  # all goldens (asks first)

Writes results/<run_id>/meta.json and runs.jsonl (one line per golden: trace_id,
timing, and the pipeline's Claude calls and cost from the trace). A golden whose
trace was not saved (trace_id None) or whose run raised is logged and skipped.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

import eval_config as config
from guard import EnvGuardError
from loaders import FixtureError, load_goldens, load_persona, load_users, persona_slugs


def git_state() -> dict[str, Any]:
    def run(*cmd: str) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=config.EVALS_DIR, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""
    return {"commit": run("git", "rev-parse", "--short", "HEAD"), "dirty": bool(run("git", "status", "--porcelain"))}


def summarize_llm_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Tokens and cost of a trace's llm_calls, priced from eval_config."""
    from llm import client as llm_client

    constant_by_model = {llm_client.SONNET: "SONNET", llm_client.HAIKU: "HAIKU"}
    tokens_in = sum(c.get("input_tokens", 0) for c in calls)
    tokens_out = sum(c.get("output_tokens", 0) for c in calls)
    cost = sum(
        config.call_cost(constant_by_model[c["model"]], c.get("input_tokens", 0), c.get("output_tokens", 0))
        for c in calls
    )
    return {"calls": len(calls), "input_tokens": tokens_in, "output_tokens": tokens_out, "cost_usd": round(cost, 6)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quality", choices=["standard", "polished"], required=True)
    parser.add_argument("--only", action="append", help="golden id (repeatable); default: all")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args(argv)

    try:
        users = load_users()
        personas = {s: load_persona(s) for s in persona_slugs()}
        goldens = load_goldens(personas=personas)
        if args.only:
            unknown = sorted(set(args.only) - {g["id"] for g in goldens})
            if unknown:
                raise FixtureError(f"unknown golden id(s): {unknown}")
            goldens = [g for g in goldens if g["id"] in args.only]
        targets = {g["persona"]: users[g["persona"]] for g in goldens}
        env.verify_auth_users(targets)
        env.verify_anthropic_key()
        client = env.backend_client()
    except (EnvGuardError, FixtureError) as exc:
        print(f"refusing to run: {exc}", file=sys.stderr)
        return 2

    per_golden = {"standard": "~$0.05-0.07", "polished": "~$0.07-0.17"}[args.quality]
    if len(goldens) > 1 and not args.yes:
        answer = input(f"Run {len(goldens)} goldens at quality={args.quality} ({per_golden} each) "
                       f"against {env.CONFIG.project_ref}? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return 1

    from pipeline.graph import run_pipeline

    run_id = f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{args.quality}"
    out_dir = config.RESULTS_DIR / run_id
    out_dir.mkdir(parents=True)
    meta = {
        "run_id": run_id,
        "quality": args.quality,
        "project_ref": env.CONFIG.project_ref,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "golden_ids": [g["id"] for g in goldens],
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Run {run_id}: {len(goldens)} golden(s) -> {out_dir}")

    ok = 0
    with (out_dir / "runs.jsonl").open("a") as runs:
        for g in goldens:
            user_id = users[g["persona"]]
            row: dict[str, Any] = {"golden_id": g["id"], "persona": g["persona"], "difficulty": g["difficulty"]}
            start = time.perf_counter()
            try:
                result = run_pipeline(
                    topic=g["topic"], format=g["format"], tone=g["tone"], length=g["length"],
                    context=g["context"], quality=args.quality, user_id=user_id,
                )
                row["seconds"] = round(time.perf_counter() - start, 1)
                row["trace_id"] = result.get("trace_id")
                if not row["trace_id"]:
                    row["status"] = "no_trace"
                    print(f"  {g['id']}: SKIPPED, trace was not saved (trace_id None)")
                else:
                    trace = (client.table("generation_traces").select("llm_calls")
                             .eq("id", row["trace_id"]).eq("user_id", user_id).execute().data or [{}])[0]
                    row["status"] = "ok"
                    row["pipeline"] = summarize_llm_calls(trace.get("llm_calls") or [])
                    row["score"] = result.get("score")
                    row["retrieval_confidence"] = result.get("retrieval_confidence")
                    ok += 1
                    print(f"  {g['id']}: ok in {row['seconds']}s, {row['pipeline']['calls']} Claude calls, "
                          f"${row['pipeline']['cost_usd']:.4f}")
            except Exception as exc:  # one failing golden must not stop the run
                row["seconds"] = round(time.perf_counter() - start, 1)
                row["status"] = "error"
                row["error"] = f"{type(exc).__name__}: {exc}"
                print(f"  {g['id']}: ERROR {row['error']}")
            runs.write(json.dumps(row) + "\n")
            runs.flush()

    print(f"Done: {ok}/{len(goldens)} ok. Next: python judge.py {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
