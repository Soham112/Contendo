"""The review regression set: fixtures/review_cases.jsonl run against the
review model. This is the development set the review prompt was written
against, so it shows regressions and nothing about how the review generalises;
it is not part of the ablation decision.

From the evals folder, with the backend venv:
    python review_regression.py                      # REVIEW_MODEL (backend/llm/models.py); asks first
    python review_regression.py --model SONNET_5_5 --yes

Each case is one marked post and one source. A case passes when the review ran,
raised every issue type in `must` and none in `must_not`. Any other type raised
is listed as "other" for a person to judge. Writes
results/review-regression/<time>-<model>.jsonl and prints one line per case.
With --ablation NAME it writes results/ablations/NAME/review-regression.jsonl
instead, and its cost counts against that ablation's spend cap (spend.py).
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

import eval_config as config
import spend
from guard import EnvGuardError
from loaders import FixtureError, load_persona, load_users

CASES_FILE = config.EVALS_DIR / "fixtures" / "review_cases.jsonl"
OUT_DIR = config.RESULTS_DIR / "review-regression"
ABLATION_FILE = "review-regression.jsonl"


def verdict(case: dict[str, Any], outcome: str, raised: set[str]) -> dict[str, Any]:
    """Pass or fail for one case, from the review's outcome and the issue types it raised."""
    missing = sorted(set(case["must"]) - raised)
    forbidden = sorted(set(case["must_not"]) & raised)
    return {"passed": outcome != "not_reviewed" and not missing and not forbidden, "missing": missing,
            "forbidden": forbidden, "other": sorted(raised - set(case["must"]) - set(case["must_not"]))}


def case_state(case: dict[str, Any], profile: dict[str, Any], user_id: str, model: str) -> dict[str, Any]:
    """The state review_post reads for a case: its post's spans and its one source as S1."""
    from llm.models import role_models
    from utils.citations import strip_citations
    from utils.formatters import GENERAL_ARCHETYPE
    from utils.frames import build_sources_block, decide_perspective

    chunks = [dict(case["source"])]
    return {
        "user_id": user_id, "topic": case["topic"], "context": "", "profile": profile,
        "perspective": decide_perspective(chunks, profile, opinion_only=False), "archetype": GENERAL_ARCHETYPE,
        "retrieval_bundle": {"chunks": chunks}, "source_index": build_sources_block(chunks, profile).index,
        "citations": [span.as_dict() for span in strip_citations(case["post"]).spans],
        "models": role_models("B", {"review": model}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="REVIEW_MODEL", help="a model constant in backend/llm/models.py")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    spend.add_arguments(parser)
    args = parser.parse_args(argv)

    from llm import models

    cases = [json.loads(line) for line in CASES_FILE.read_text().splitlines() if line.strip()]
    try:
        model = getattr(models, args.model, None)
        if model not in models.MODELS:
            raise FixtureError(f"--model {args.model!r} is not a model constant in backend/llm/models.py")
        users = load_users()
        profiles = {slug: load_persona(slug).profile for slug in {case["persona"] for case in cases}}
        env.verify_anthropic_key()
        env.backend_client()        # checks the backend points at the eval project (usage rows go there)
    except (EnvGuardError, FixtureError) as exc:
        print(f"refusing to run: {exc}", file=sys.stderr)
        return 2
    if not args.yes:
        answer = input(f"Review {len(cases)} cases with {model} (about $0.01-0.02 each)? [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return 1

    from agents.review_agent import review_post
    from llm.client import trace_calls
    from llm.pricing import call_cost

    cap = spend.open_cap(args.ablation, args.spend_cap, call_cost)
    if args.ablation:
        out_path = config.ABLATIONS_DIR / args.ablation / ABLATION_FILE
    else:
        out_path = OUT_DIR / f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{model}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    passed = 0
    cost = 0.0
    with out_path.open("a") as out:
        for case in cap.guard(cases, lambda case, done: f"review regression set before {case['id']}: "
                                                        f"{done} of {len(cases)} cases run"):
            with trace_calls() as calls:
                review = review_post(case_state(case, profiles[case["persona"]], users[case["persona"]], model))
            raised = {issue["type"] for issue in review["issues"]}
            result = verdict(case, review["outcome"], raised)
            cost += sum(call_cost(c["model"], c["input_tokens"], c["output_tokens"]) for c in calls)
            cap.record(calls, f"review regression {case['id']}")
            passed += result["passed"]
            out.write(json.dumps({"id": case["id"], "model": model, "outcome": review["outcome"],
                                  "error": review.get("error"), "raised": sorted(raised), **result,
                                  "records": review["records"], "invalid": review["invalid"]}) + "\n")
            out.flush()
            detail = "; ".join(f"{key} {result[key]}" for key in ("missing", "forbidden", "other") if result[key])
            if review["outcome"] == "not_reviewed":
                detail = f"not reviewed: {review.get('error')}"
            print(f"  {'PASS' if result['passed'] else 'FAIL'}  {case['id']:<32} {detail}")
    print(f"{passed}/{len(cases)} passed with {model}; ${cost:.4f}. Development set: not part of the ablation decision.\n{out_path}")
    return spend.STOPPED_EXIT if cap.stopped_at else 0


if __name__ == "__main__":
    sys.exit(main())
