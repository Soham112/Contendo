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
    parser.add_argument("--metric-judge", action="append", default=[], metavar="METRIC=MODEL",
                        help="take this metric from another judge model's scores, e.g. unsupported_specifics=SONNET")
    args = parser.parse_args(argv)
    metric_judges = {}
    for item in args.metric_judge:
        metric, _, model = item.partition("=")
        if metric not in config.METRIC_ORDER or model not in config.SCORES_FILES:
            parser.error(f"--metric-judge {item!r}: expected METRIC=MODEL with a known metric and judge model")
        metric_judges[metric] = model

    run_dir = config.RESULTS_DIR / args.run_id
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        print(f"no meta.json in {run_dir}", file=sys.stderr)
        return 2
    suffix = "" if args.judge_model == config.JUDGE_MODEL else f"-{args.judge_model.lower()}"
    if metric_judges:
        suffix += "-mixed"

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
            [row for model in {args.judge_model, *metric_judges.values()}
             for row in read_jsonl(run_dir / config.SCORES_FILES[model])],
            {g["id"]: g for g in load_goldens()},
            judge_model=args.judge_model,
            metric_judges=metric_judges,
        )
        out = run_dir / f"report{suffix}.md"
    out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
