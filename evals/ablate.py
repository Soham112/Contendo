"""The full ablation in one command, under one spend cap.

From the evals folder, with the backend venv:
    python ablate.py --name full                 # shows the plan and the cap, asks first
    python ablate.py --name full --yes
    python ablate.py --name smoke2 --only pm-05 --only ds-01 --variants A C --spend-cap 1

In order:
  1. run.py for each variant (eval_config.ABLATION_VARIANTS: A, C, B-Opus,
     C-Opus), every golden;
  2. judge.py on each run: unsupported_specifics with SONNET, then
     answer_relevancy with the default judge (eval_config.ABLATION_JUDGES);
  3. review_regression.py once, on REVIEW_MODEL (development set; not part of
     the decision);
  4. report.py --variants: results/ablations/<name>/ablation.md.
The instrument (instrument.py) is not part of it: it uses B's own reviewer, so
it favours B by construction and cannot decide between the variants.

Every step is run with --ablation <name>, so all of them add to one ledger
(results/ablations/<name>/spend.json) and stop before the next post once the
cap is reached (spend.py). When a step stops there, nothing after it is started;
the report is still written from what exists. Running the command again reuses
the runs this ablation already has (a run the cap cut short stays as it is), and
judging continues from the cache: raise --spend-cap to let it go on.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import json
import sys

import eval_config as config
import judge
import report
import review_regression
import run
import spend
from reporting import read_jsonl


def ablation_runs(name: str) -> dict[str, str]:
    """variant -> run id, for the runs that belong to this ablation (the first one made per variant)."""
    found: dict[str, str] = {}
    for meta_path in sorted(config.RESULTS_DIR.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text())
        if meta.get("ablation") == name and meta.get("variant") not in found:
            found[meta["variant"]] = meta["run_id"]
    return found


def run_steps(name: str, variants: list[str], only: list[str], cap: float,
              existing: dict[str, str]) -> list[tuple[str, list[str] | None]]:
    """The pipeline runs to make, as (description, run.py arguments); None marks
    a variant this ablation already has a run for."""
    common = ["--ablation", name, "--spend-cap", str(cap)]
    plan: list[tuple[str, list[str] | None]] = []
    for variant in variants:
        args = ["--quality", "standard", "--variant", variant, "--yes", *common, *(a for g in only for a in ("--only", g))]
        plan.append((f"run {variant}", None if variant in existing else args))
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="the ablation's folder in results/ablations/")
    parser.add_argument("--variants", nargs="+", default=list(config.ABLATION_VARIANTS))
    parser.add_argument("--only", action="append", default=[], help="golden id (repeatable); default: all")
    parser.add_argument("--spend-cap", type=float, default=config.EVAL_SPEND_CAP_USD, metavar="USD")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args(argv)

    from llm.pricing import call_cost

    cap = spend.open_cap(args.name, args.spend_cap, call_cost)
    existing = ablation_runs(args.name)
    print(f"Ablation {args.name!r}: variants {', '.join(args.variants)}; "
          f"{'goldens ' + ', '.join(args.only) if args.only else 'all goldens'}.\n"
          f"Judges: unsupported_specifics ({config.ABLATION_JUDGES['unsupported_specifics']}), "
          f"answer_relevancy ({config.ABLATION_JUDGES['answer_relevancy']}); then the review regression set.\n"
          f"Spend cap ${args.spend_cap:.2f}; already spent ${cap.spent_usd:.2f}. "
          f"Runs already made: {existing or 'none'}. Project {env.CONFIG.project_ref}.")
    if cap.reached:
        print(cap.stop("before starting: the ledger is already at the cap"))
        return spend.STOPPED_EXIT
    if not args.yes and input("Start? [y/N] ").strip().lower() != "y":
        print("Aborted.")
        return 1

    common = ["--ablation", args.name, "--spend-cap", str(args.spend_cap)]
    stopped = False
    for description, step_args in run_steps(args.name, args.variants, args.only, args.spend_cap, existing):
        if step_args is None:
            print(f"== {description}: already in this ablation, reused")
            continue
        print(f"== {description}")
        code = run.main(step_args)
        if code not in (0, spend.STOPPED_EXIT):
            print(f"{description} failed (exit {code}); stopping.", file=sys.stderr)
            return code
        if code == spend.STOPPED_EXIT:
            stopped = True
            break

    runs = ablation_runs(args.name)
    run_ids = [runs[v] for v in args.variants if v in runs]
    for metric, model in ([] if stopped else config.ABLATION_JUDGES.items()):
        for run_id in run_ids:
            print(f"== judge {metric} ({model}) on {run_id}")
            code = judge.main([run_id, "--judge-model", model, "--metric", metric, *common])
            if code not in (0, spend.STOPPED_EXIT):
                print(f"judging {run_id} failed (exit {code}); stopping.", file=sys.stderr)
                return code
            if code == spend.STOPPED_EXIT:
                stopped = True
                break
        if stopped:
            break

    regression = config.ABLATIONS_DIR / args.name / review_regression.ABLATION_FILE
    cases = sum(1 for line in review_regression.CASES_FILE.read_text().splitlines() if line.strip())
    if not stopped and len(read_jsonl(regression)) < cases:
        print("== review regression set")
        regression.unlink(missing_ok=True)          # a set the cap cut short is run again whole
        code = review_regression.main(["--yes", *common])
        if code not in (0, spend.STOPPED_EXIT):
            return code
        stopped = code == spend.STOPPED_EXIT

    if run_ids:
        report.write_ablation(run_ids, args.name)
    final = spend.open_cap(args.name, args.spend_cap, call_cost)
    print(f"\nAblation {args.name!r}: ${final.spent_usd:.2f} spent of a ${args.spend_cap:.2f} cap."
          + (" STOPPED AT THE CAP; see the last 'SPEND CAP REACHED' line above." if stopped else " Finished."))
    return spend.STOPPED_EXIT if stopped else 0


if __name__ == "__main__":
    sys.exit(main())
