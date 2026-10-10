"""Markdown report for a judged run. Reads only files; never re-judges.

From the evals folder, with the backend venv:
    python report.py <run_id>                                   # report.md (default judge)
    python report.py <run_id> --judge-model SONNET              # report-sonnet.md
    python report.py <run_id> --judge-model HAIKU --compare SONNET   # compare-haiku-sonnet.md
    python report.py --variants <run A> <run B> <run C> <run B-Opus> --name smoke   # the ablation

Writes the markdown into results/<run_id>/ and prints it. --variants writes
results/ablations/<name>/ablation.md and ablation.json (the runs compared, which
blind.py reads); run it again after `blind.py score` to add the audit and the
blind read.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import json
import sys

import eval_config as config
from ablation import build_ablation
from loaders import load_goldens
from reporting import build_judge_comparison, build_report, read_jsonl


def _read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def write_ablation(run_ids: list[str], name: str) -> int:
    """ablation.md for these runs, one per variant, in the order given."""
    variants = []
    for run_id in run_ids:
        run_dir = config.RESULTS_DIR / run_id
        meta = _read_json(run_dir / "meta.json")
        if meta is None or "variant" not in meta:
            print(f"{run_dir}: no meta.json with a variant (a run made with run.py --variant)", file=sys.stderr)
            return 2
        variants.append({
            "meta": meta,
            "runs": read_jsonl(run_dir / "runs.jsonl"),
            "scores": {model: read_jsonl(run_dir / config.SCORES_FILES[model])
                       for model in set(config.ABLATION_JUDGES.values())},
            "instrument": read_jsonl(run_dir / config.INSTRUMENT_FILE),
        })
    out_dir = config.ABLATIONS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ablation.json").write_text(json.dumps({"name": name, "runs": run_ids}, indent=2) + "\n")
    text = build_ablation(name, variants, audit=_read_json(out_dir / "audit.json"), blind=_read_json(out_dir / "blind.json"))
    (out_dir / "ablation.md").write_text(text)
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--variants", nargs="+", metavar="RUN_ID", help="write the ablation report for these runs")
    parser.add_argument("--name", help="with --variants: the folder in results/ablations/ (default: the first run id)")
    parser.add_argument("--judge-model", choices=sorted(config.SCORES_FILES), default=config.JUDGE_MODEL)
    parser.add_argument("--compare", choices=sorted(config.SCORES_FILES),
                        help="also compare against this judge model, on the goldens both judged")
    parser.add_argument("--metric-judge", action="append", default=[], metavar="METRIC=MODEL",
                        help="take this metric from another judge model's scores, e.g. unsupported_specifics=SONNET")
    args = parser.parse_args(argv)
    if args.variants:
        return write_ablation(args.variants, args.name or args.variants[0])
    if not args.run_id:
        parser.error("give a run id, or --variants <run ids>")
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
