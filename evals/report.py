"""Markdown report for a judged run. Reads only files; never re-judges.

From the evals folder, with the backend venv:
    python report.py <run_id>                                   # report.md (default judge)
    python report.py <run_id> --judge-model SONNET              # report-sonnet.md
    python report.py <run_id> --judge-model HAIKU --compare SONNET   # compare-haiku-sonnet.md

Writes the markdown into results/<run_id>/ and prints it.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import json
import sys

import eval_config as config
from loaders import load_goldens
from reporting import build_judge_comparison, build_report, read_jsonl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id")
    parser.add_argument("--judge-model", choices=sorted(config.SCORES_FILES), default=config.JUDGE_MODEL)
    parser.add_argument("--compare", choices=sorted(config.SCORES_FILES),
                        help="also compare against this judge model, on the goldens both judged")
    args = parser.parse_args(argv)

    run_dir = config.RESULTS_DIR / args.run_id
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        print(f"no meta.json in {run_dir}", file=sys.stderr)
        return 2
    suffix = "" if args.judge_model == config.JUDGE_MODEL else f"-{args.judge_model.lower()}"

    if args.compare:
        text = build_judge_comparison(
            read_jsonl(run_dir / config.SCORES_FILES[args.judge_model]),
            read_jsonl(run_dir / config.SCORES_FILES[args.compare]),
            args.judge_model, args.compare, args.run_id,
        )
        out = run_dir / f"compare-{args.judge_model.lower()}-{args.compare.lower()}.md"
    else:
        text = build_report(
            json.loads(meta_path.read_text()),
            read_jsonl(run_dir / "runs.jsonl"),
            read_jsonl(run_dir / config.SCORES_FILES[args.judge_model]),
            {g["id"]: g for g in load_goldens()},
            judge_model=args.judge_model,
        )
        out = run_dir / f"report{suffix}.md"
    out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
