"""Instrument for the ablation: the acting issues the review finds on each
variant's FINAL post. Record-only: nothing is changed, and no decision rests on
it alone, because it is the same reviewer B was fixed against, so it is biased
in B's favour.

From the evals folder, with the backend venv:
    python instrument.py <run_id>            # asks first when it will call Claude
    python instrument.py <run_id> --yes

Writes results/<run_id>/instrument.jsonl, one line per returned post:
- a variant that reviews (B, B-Opus): no call. The line is the pipeline's own
  last review of the returned post, as run.py stored it.
- any other variant (A, C): the review (agents.review_agent.review_post, B's
  review model) is run once on the final post, rebuilt from its trace. A's
  posts have no citations, so every one of its sentences is reviewed as
  uncited; the report keeps the citation-only issue type apart for that reason.
A post that already has a reviewed line is not reviewed again. A review that
did not happen (a call failed, or its answer could not be used) is written with
status "not_reviewed" and its reason, and is tried again on the next run; the
report reads the last line per post.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import json
import sys
from collections import Counter
from typing import Any

import ablation
import eval_config as config
from guard import EnvGuardError
from loaders import FixtureError, load_users
from reporting import read_jsonl


class InstrumentError(RuntimeError):
    """A trace cannot be turned back into what the review needs."""


def review_state(trace: dict[str, Any], user_id: str) -> dict[str, Any]:
    """The state review_post reads, rebuilt from a generation trace.

    The sources are the trace's chunk snapshots, numbered as the single-writer
    sources block numbers them. The trace stored each chunk's authorship when
    the post was written; if the rebuilt index disagrees with it, or with the
    index a single-writer run stored, the snapshot does not reproduce what the
    drafter saw and the post is not reviewed."""
    from llm.models import role_models
    from utils.citations import strip_citations
    from utils.frames import build_sources_block

    outputs, chunks, profile = trace["node_outputs"], trace["retrieved"], trace["profile_snapshot"]
    index = build_sources_block(chunks, profile).index
    stored = outputs.get("source_index")
    if stored is not None and stored != index:
        raise InstrumentError("the source index rebuilt from the trace differs from the one the run stored")
    for sid, entry in index.items():
        if chunks[entry["position"]]["authorship"] != entry["authorship"]:
            raise InstrumentError(f"{sid}: authorship rebuilt from the trace differs from the one stored with it")
    post = outputs["final_post"]
    return {
        "user_id": user_id, "topic": trace["topic"], "context": trace["context"], "profile": profile,
        "perspective": outputs["perspective"], "archetype": trace["archetype"], "event": outputs.get("event"),
        "retrieval_bundle": {"chunks": chunks}, "source_index": index,
        "citations": outputs.get("citations") or [span.as_dict() for span in strip_citations(post).spans],
        "models": role_models("B"),
    }


def reviewed_line(review: dict[str, Any], calls: list[dict[str, Any]]) -> dict[str, Any]:
    """An instrument line from a review_post result: the issue types that act (pipeline.redraft)."""
    from llm.pricing import call_cost
    from pipeline.redraft import split_issues

    acting, _ = split_issues({"issues": []}, review)
    status = "not_reviewed" if review["outcome"] == "not_reviewed" else "ok"
    return {"status": status, "source": "review of the final post", "outcome": review["outcome"],
            "acting": dict(Counter(issue["type"] for issue in acting)), "unreviewed": len(review["unreviewed"]),
            "error": review.get("error"), **{k: v for k, v in ablation.summarize_llm_calls(calls, call_cost).items()
                                             if k != "by_model"}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args(argv)

    run_dir = config.RESULTS_DIR / args.run_id
    posts = [row for row in read_jsonl(run_dir / "runs.jsonl") if row.get("status") == "ok"]
    if not posts:
        print(f"no returned posts in {run_dir}", file=sys.stderr)
        return 2
    out_path = run_dir / config.INSTRUMENT_FILE
    done = {(row["golden_id"], row["trace_id"]) for row in read_jsonl(out_path) if row["status"] == "ok"}
    pending = [row for row in posts if (row["golden_id"], row["trace_id"]) not in done]
    to_review = [row for row in pending if row["record"]["route"] is None]
    try:
        users = load_users()
        if to_review:
            env.verify_anthropic_key()
        client = env.backend_client()
    except (EnvGuardError, FixtureError) as exc:
        print(f"refusing to run: {exc}", file=sys.stderr)
        return 2
    if to_review and not args.yes:
        answer = input(f"Review {len(to_review)} final post(s) of {args.run_id} with B's review model "
                       f"(about $0.05-0.08 each) against {env.CONFIG.project_ref}? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return 1

    from agents.review_agent import review_post
    from llm.client import trace_calls

    with out_path.open("a") as out:
        for row in pending:
            line = {"golden_id": row["golden_id"], "trace_id": row["trace_id"], "variant": row["variant"]}
            record = row["record"]
            if record["route"] is not None:
                line.update(status="ok", source="the pipeline's own last review", outcome=record["outcome"],
                            acting=record["remaining"], unreviewed=record["unreviewed"], calls=0, cost_usd=0.0)
            else:
                user_id = users[row["persona"]]
                try:
                    trace = (client.table("generation_traces").select("*")
                             .eq("id", row["trace_id"]).eq("user_id", user_id).execute().data or [None])[0]
                    if trace is None:
                        raise InstrumentError(f"trace {row['trace_id']} not found")
                    with trace_calls() as calls:
                        review = review_post(review_state(trace, user_id))
                    line.update(reviewed_line(review, calls))
                except Exception as exc:  # one post must not stop the rest; the line says what failed
                    line.update(status="error", error=f"{type(exc).__name__}: {exc}")
            out.write(json.dumps(line) + "\n")
            out.flush()
            shown = line["acting"] if line["status"] == "ok" else line["error"]
            print(f"  {line['golden_id']:<12} {line['status']:<6} {shown}")
    print(f"Instrument: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
