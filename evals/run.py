"""Run goldens through the real pipeline as their persona.

From the evals folder, with the backend venv:
    python run.py --quality standard --only pm-01     # one golden
    python run.py --quality standard                  # all goldens (asks first)
    python run.py --quality standard --variant B-Opus # one pipeline variant (default: PIPELINE_VARIANT, else A)
    python run.py --quality standard --variant B --model small=HAIKU_5_5   # a role model for this run only

Writes results/<run_id>/meta.json (the variant and its models included) and
runs.jsonl: one line per golden with trace_id, timing, the pipeline's Claude
calls and cost from the trace, the post, its sources, and what the ablation
report reads (ablation.post_record). A golden whose trace was not saved
(trace_id None) or whose run raised is logged and skipped.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

import ablation
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
    """Tokens and cost of a trace's llm_calls, priced from the backend's price table."""
    from llm.pricing import call_cost

    return ablation.summarize_llm_calls(calls, call_cost)


def parse_role_models(items: list[str]) -> dict[str, str]:
    """--model ROLE=CONSTANT pairs as {role: model id}; CONSTANT names a model
    in backend/llm/models.py (e.g. HAIKU_5_5)."""
    from llm import models

    chosen = {}
    for item in items:
        role, _, constant = item.partition("=")
        model = getattr(models, constant, None)
        if role not in models.ROLE_MODELS or model not in models.MODELS:
            raise FixtureError(f"--model {item!r}: expected ROLE=CONSTANT, with ROLE in {sorted(models.ROLE_MODELS)} "
                               "and CONSTANT a model id constant in backend/llm/models.py")
        chosen[role] = model
    return chosen


def trace_fields(trace: dict[str, Any]) -> dict[str, Any]:
    """What a runs.jsonl row keeps of a trace, so the report and blind.py need no database."""
    import metrics
    from utils.citations import prose_word_count, source_id
    from utils.formatters import count_words

    outputs, calls = trace.get("node_outputs") or {}, trace.get("llm_calls") or []
    return {
        "pipeline": summarize_llm_calls(calls),
        "record": ablation.post_record(outputs, calls, {"count_words": count_words, "prose_word_count": prose_word_count}),
        "post": outputs.get("final_post") or "",
        "sources": [{"id": source_id(position), "title": chunk.get("source_title", ""), "text": chunk.get("text", "")}
                    for position, chunk in enumerate(trace.get("retrieved") or [])],
        "profile_text": metrics.profile_text(trace.get("profile_snapshot") or {}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quality", choices=["standard", "polished"], required=True)
    parser.add_argument("--variant", help="pipeline variant (config.features.PIPELINE_VARIANTS); "
                                          "default: PIPELINE_VARIANT from evals/.env, else A")
    parser.add_argument("--model", action="append", default=[], metavar="ROLE=CONSTANT",
                        help="single-writer variants only: use this model for a role in this run, e.g. small=HAIKU_5_5")
    parser.add_argument("--only", action="append", help="golden id (repeatable); default: all")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args(argv)

    from config import features
    from llm import client as llm_client
    from llm import models

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
        variant = features.pipeline_variant() if args.variant is None else features.validate_pipeline_variant(args.variant)
        overrides = parse_role_models(args.model)
        if features.VARIANT_GRAPH[variant] == "A":
            if overrides:
                raise FixtureError("--model applies to the single-writer variants; pipeline A uses fixed models")
            run_models = {"pipeline_a": [llm_client.SONNET, llm_client.HAIKU]}
        else:
            run_models = models.role_models(variant, overrides)
    except (EnvGuardError, FixtureError, features.PipelineConfigError, models.ModelConfigError) as exc:
        print(f"refusing to run: {exc}", file=sys.stderr)
        return 2

    per_golden = {"standard": "~$0.05-0.07", "polished": "~$0.07-0.17"}[args.quality]
    if len(goldens) > 1 and not args.yes:
        answer = input(f"Run {len(goldens)} goldens, variant {variant}, at quality={args.quality} ({per_golden} each) "
                       f"against {env.CONFIG.project_ref}? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return 1

    from pipeline.graph import run_pipeline

    tag = variant + "".join(f"-{role}-{constant}" for role, _, constant in (item.partition("=") for item in args.model))
    run_id = f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{args.quality}-{tag}"
    out_dir = config.RESULTS_DIR / run_id
    out_dir.mkdir(parents=True)
    meta = {
        "run_id": run_id,
        "quality": args.quality,
        "variant": variant,
        "models": run_models,
        "model_overrides": overrides,
        "project_ref": env.CONFIG.project_ref,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "golden_ids": [g["id"] for g in goldens],
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Run {run_id}: {len(goldens)} golden(s), variant {variant} -> {out_dir}")

    ok = 0
    with (out_dir / "runs.jsonl").open("a") as runs:
        for g in goldens:
            user_id = users[g["persona"]]
            row: dict[str, Any] = {"golden_id": g["id"], "persona": g["persona"], "difficulty": g["difficulty"],
                                   "variant": variant}
            start = time.perf_counter()
            try:
                result = run_pipeline(
                    topic=g["topic"], format=g["format"], tone=g["tone"], length=g["length"],
                    context=g["context"], quality=args.quality, user_id=user_id,
                    variant=variant, models=overrides or None,
                )
                row["seconds"] = round(time.perf_counter() - start, 1)
                if result.get("fact_check_job"):  # log-only fact check, outside the timing (as in /generate)
                    result["fact_check_job"]()
                row["trace_id"] = result.get("trace_id")
                if result.get("status") == "low_coverage":
                    row["status"] = "gated"
                    row["closest_sources"] = [s["title"] for s in result.get("closest_sources", [])]
                    print(f"  {g['id']}: GATED (low coverage) in {row['seconds']}s")
                elif not row["trace_id"]:
                    row["status"] = "no_trace"
                    print(f"  {g['id']}: SKIPPED, trace was not saved (trace_id None)")
                else:
                    trace = (client.table("generation_traces")
                             .select("llm_calls,node_outputs,retrieved,profile_snapshot")
                             .eq("id", row["trace_id"]).eq("user_id", user_id).execute().data or [{}])[0]
                    # "ok", or a single-writer run that returned no post: draft_truncated, draft_refused.
                    row["status"] = result.get("status", "ok")
                    row.update(trace_fields(trace))
                    # Background (log-only) fact check, as written to the trace by fact_check_job.
                    fc = (trace.get("node_outputs") or {}).get("fact_check") or {}
                    row["fact_check"] = {
                        "mode": fc.get("mode"), "outcome": fc.get("outcome"),
                        "flagged": [{"type": f.get("type"), "why": f.get("why"), "sentence": f.get("sentence")}
                                    for f in fc.get("flagged") or []],
                    }
                    row["score"] = result.get("score")
                    row["retrieval_confidence"] = result.get("retrieval_confidence")
                    ok += row["status"] == "ok"
                    print(f"  {g['id']}: {row['status']} in {row['seconds']}s, {row['pipeline']['calls']} Claude calls, "
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
