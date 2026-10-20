"""Measure the provenance classifier (step 3.3) on the provenance test set.

From the repo root, with the backend venv:
    backend/venv/bin/python evals/provenance_eval.py --check                    # validate labels; $0
    backend/venv/bin/python evals/provenance_eval.py --estimate                 # expected cost; $0, no network
    backend/venv/bin/python evals/provenance_eval.py --estimate --count-tokens  # exact input tokens (free API call)
    backend/venv/bin/python evals/provenance_eval.py --run --name <date>-<label> [--spend-cap 1.00]   # PAID, asks first
    backend/venv/bin/python evals/provenance_eval.py --run --name <name> --resume   # continue after an error, same cap
    backend/venv/bin/python evals/provenance_eval.py --rescore <name> [--agreement-with <other name>]

The classifier runs on fixture text directly: no seeding, no database writes,
no embeddings. Results go to results/provenance/<name>/ (results.jsonl,
report.md, spend.json). Spend is measured from the calls' usage and the run
stops before the next case once it reaches the cap.
"""
import env  # noqa: F401  (must be the first project import)

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import eval_config as config
import provenance_fixtures as pf
import provenance_metrics as pm
from spend import SpendCap

RUNS_DIR = config.RESULTS_DIR / "provenance"
EVAL_USER = "eval-provenance"
DEFAULT_SPEND_CAP_USD = 1.00

def _prepared(case: pf.Case) -> dict[str, Any]:
    """The classifier's inputs for a case, and its labels per paragraph."""
    from agents.provenance_agent import author_context_from
    from agents.provenance_prompt import SourceFacts
    from utils.provenance_spans import paragraphs

    paras = paragraphs(case.content)
    sizes = {p.id: p.end - p.start for p in paras}
    try:
        truth = pm.paragraph_truth(case.authorship, case.authorship_other, sizes)
    except ValueError as e:
        raise SystemExit(f"{case.id}: {e}")
    facts = SourceFacts(title=case.title, title_origin=case.title_origin, input_type=case.input_type,
                        source_type=case.source_type, provider_author=case.author)
    return {"case": case, "paragraphs": [(p.id, p.start, p.end) for p in paras], "sizes": sizes,
            "truth": truth, "facts": facts, "author": author_context_from(*pf.persona_details(case.persona))}


def _count_tokens(prepared: dict[str, Any]) -> list[int]:
    """Exact input tokens per call from the token-counting endpoint (free)."""
    from agents.provenance_agent import TOOL_DESCRIPTION, TOOL_NAME, plan_requests, reading_schema
    from agents.provenance_prompt import SYSTEM_PROMPT
    from llm.client import HAIKU, client

    tool = {"name": TOOL_NAME, "description": TOOL_DESCRIPTION,
            "input_schema": reading_schema(prepared["facts"]).model_json_schema()}
    return [client.messages.count_tokens(model=HAIKU, system=SYSTEM_PROMPT, tools=[tool],
                                         tool_choice={"type": "tool", "name": TOOL_NAME},
                                         messages=[{"role": "user", "content": r.message}]).input_tokens
            for r in plan_requests(prepared["case"].content, facts=prepared["facts"], author=prepared["author"])]


def estimate(prepared: list[dict[str, Any]], count_tokens: bool = False) -> dict[str, Any]:
    """Expected and upper-bound USD for one run (provenance_agent.call_costs)."""
    from agents.provenance_agent import call_costs, estimated_tokens, request_chars

    pairs: list[tuple[int, int]] = []
    for p in prepared:
        if count_tokens:
            pairs += [(t, t) for t in _count_tokens(p)]
        else:
            pairs += [estimated_tokens(c) for c in request_chars(p["case"].content, facts=p["facts"],
                                                                  author=p["author"])]
    calls, tokens_in, expected, upper = call_costs(pairs)
    return {"cases": len(prepared), "calls": calls, "input_tokens": tokens_in,
            "expected_usd": expected, "upper_usd": upper, "counted": count_tokens}


def _record(prepared: dict[str, Any], result: Any, cost: float) -> dict[str, Any]:
    case = prepared["case"]
    answer = None
    if result is not None:
        answer = {"authorship": result.authorship, "confident": result.confident,
                  "paragraphs": pm.predicted_paragraphs(result.authorship, result.spans, prepared["paragraphs"]),
                  "spans": result.spans, "reasons": result.reasons,
                  "readings": [r.model_dump() for r in result.readings],
                  "failed_samples": result.failures}
    return {"id": case.id, "persona": case.persona, "split": case.split, "origin": case.origin,
            "tests": case.tests, "truth": case.authorship, "truth_paragraphs": prepared["truth"],
            "sizes": prepared["sizes"], "result": answer, "cost_usd": round(cost, 6)}


def run(prepared: list[dict[str, Any]], out: Path, cap_usd: float) -> tuple[list[dict[str, Any]], str | None]:
    """Classify every case not already in out/results.jsonl, appending to it.
    An exception stops the run: the failing case's calls are still recorded in
    the spend ledger, and the error is returned so the run can be resumed."""
    from agents.provenance_agent import classify_provenance
    from llm.client import trace_calls
    from llm.pricing import call_cost

    path = out / "results.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    done = {r["id"] for r in records}
    todo = [p for p in prepared if p["case"].id not in done]
    cap = SpendCap(out / "spend.json", cap_usd, call_cost)
    error = None
    with path.open("a") as f:
        for p in cap.guard(todo, lambda item, n: f"before {item['case'].id} ({len(done) + n} of {len(prepared)} done)"):
            with trace_calls() as calls:
                try:
                    result = classify_provenance(p["case"].content, facts=p["facts"], author=p["author"],
                                                 user_id=EVAL_USER)
                except Exception as exc:
                    error = f"{p['case'].id}: {type(exc).__name__}: {exc}"
            if error:
                cap.record(calls, f"{p['case'].id} (error)")
                break
            record = _record(p, result, cap.record(calls, p["case"].id))
            records.append(record)
            f.write(json.dumps(record) + "\n")
    print(f"Measured spend: ${cap.spent_usd:.4f} (cap ${cap_usd:.2f})")
    return records, error


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def write_report(records: list[dict[str, Any]], out: Path, agreement: float | None = None) -> str:
    lines = [f"# Provenance classifier: {out.name}", "",
             "Targets: " + ", ".join(f"{k} {v}" for k, v in pm.TARGETS.items()), ""]
    for split in ("dev", "holdout", "all"):
        rows = [r for r in records if split == "all" or r["split"] == split]
        if not rows:
            continue
        scores = pm.score(rows)
        verdict = pm.verdicts(scores, agreement if split == "all" else None)
        lines += [f"## {split} ({scores['sources']} sources)", ""]
        for key in ("failed", "applied_automatically", "external_applied_as_own", "own_applied_as_external",
                    "mixed_paragraph_recall"):
            mark = {True: " (met)", False: " (MISSED)", None: ""}[verdict.get(key)]
            lines.append(f"- {key}: {_fmt(scores[key])}{mark}")
        if scores["external_applied_as_own_where"]:
            lines.append(f"  - where: {', '.join(scores['external_applied_as_own_where'])}")
        for label in pm.LABELS:
            lines.append(f"- {label}: precision {_fmt(scores['precision'][label])}, recall {_fmt(scores['recall'][label])}")
        lines += ["", "| truth \\ predicted | user_authored | external | failed |", "|---|---|---|---|"]
        lines += [f"| {t} | " + " | ".join(str(scores["confusion"][t][p]) for p in (*pm.LABELS, "failed")) + " |"
                  for t in pm.LABELS]
        lines.append("")
    if agreement is not None:
        mark = " (met)" if agreement >= pm.TARGETS["run_agreement"] else " (MISSED)"
        lines += [f"Run agreement: {agreement:.3f}{mark}", ""]
    lines += ["## Cases", "", "| id | split | truth | predicted | confident | why not confident |", "|---|---|---|---|---|---|"]
    for r in records:
        res = r["result"] or {}
        lines.append(f"| {r['id']} | {r['split']} | {r['truth']} | {res.get('authorship', 'failed')} | "
                     f"{res.get('confident', '')} | {'; '.join(res.get('reasons', []))} |")
    text = "\n".join(lines) + "\n"
    (out / "report.md").write_text(text)
    return text


def _load_records(name: str) -> list[dict[str, Any]]:
    path = RUNS_DIR / name / "results.jsonl"
    if not path.exists():
        raise SystemExit(f"no results at {path}")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate the labels; no calls")
    mode.add_argument("--estimate", action="store_true", help="expected cost of one run; no paid calls")
    mode.add_argument("--run", action="store_true", help="classify every case (paid; asks first)")
    mode.add_argument("--rescore", metavar="NAME", help="score a saved run again")
    parser.add_argument("--count-tokens", action="store_true", help="with --estimate: exact input tokens (free API)")
    parser.add_argument("--name", help="with --run: results/provenance/NAME")
    parser.add_argument("--spend-cap", type=float, default=DEFAULT_SPEND_CAP_USD, metavar="USD")
    parser.add_argument("--yes", action="store_true", help="with --run: don't ask before spending")
    parser.add_argument("--resume", action="store_true",
                        help="with --run: continue NAME, skipping finished cases (same spend ledger and cap)")
    parser.add_argument("--agreement-with", metavar="NAME", help="with --rescore: another run of the same cases")
    args = parser.parse_args(argv)

    if args.rescore:
        records = _load_records(args.rescore)
        agreement = None
        if args.agreement_with:
            other = {r["id"]: r["result"] for r in _load_records(args.agreement_with)}
            agreement = pm.agreement({r["id"]: r["result"] for r in records}, other)
        print(write_report(records, RUNS_DIR / args.rescore, agreement))
        return 0

    cases = pf.load_cases()
    prepared = [_prepared(c) for c in cases]
    splits = {s: sum(c.split == s for c in cases) for s in pf.SPLITS}
    labels = {label: sum(c.authorship == label for c in cases) for label in pm.LABELS}
    mixed = sum(bool(c.authorship_other) for c in cases)
    print(f"{len(cases)} cases: {splits}, {labels}, {mixed} mixed")
    if args.check:
        return 0

    cost = estimate(prepared, count_tokens=args.count_tokens)
    from agents.provenance_agent import CHARS_PER_TOKEN
    how = "counted" if cost["counted"] else f"estimated at {CHARS_PER_TOKEN} chars/token"
    print(f"{cost['calls']} calls, {cost['input_tokens']} input tokens ({how}). "
          f"Expected ${cost['expected_usd']:.4f}, upper bound ${cost['upper_usd']:.4f} (every call retried at max_tokens).")
    if args.estimate:
        return 0

    if not args.name:
        parser.error("--run needs --name")
    out = RUNS_DIR / args.name
    if (out / "results.jsonl").exists() and not args.resume:
        parser.error(f"{out} already has results; choose another --name, or --resume it")
    if not args.yes and input(f"Spend up to ${args.spend_cap:.2f}? [y/N] ").strip().lower() != "y":
        print("Nothing run.")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    records, error = run(prepared, out, args.spend_cap)
    print(write_report(records, out))
    if error:
        print(f"Stopped on an error: {error}\nFinished cases are kept; re-run with --resume.", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
