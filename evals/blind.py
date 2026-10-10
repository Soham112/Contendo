"""The two things only a person can judge: whether the unsupported_specifics
judge is right, and which post reads best.

From the evals folder (file-only: no backend, no network, no API cost):
    python blind.py audit <ablation>   # audit.md: 10 judge findings to mark, audit-key.json
    python blind.py make <ablation>    # read.md: 10 goldens, each variant's post, key.json
    python blind.py score <ablation>   # reads the marks back: audit.json, blind.json

<ablation> is a folder in results/ablations/ made by `report.py --variants`.
Nothing in audit.md or read.md says which variant wrote a post; the key files do.
Re-run `report.py --variants` after `score` to put the results in ablation.md.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path
from statistics import mean
from typing import Any

import eval_config as config
from reporting import _latest, read_jsonl

VERDICTS = {"correct": True, "wrong": False}     # what a `verdict:` line in audit.md may say
# A line to fill in. The entry's id is part of it, so a post that happens to
# contain a heading or a "note:" line of its own cannot be read as an answer.
_FIELD = "{name}[{entry}]:"


class BlindError(RuntimeError):
    """A file this step needs is missing or cannot be read as written."""


def load_variants(ablation_dir: Path, results_dir: Path = config.RESULTS_DIR) -> list[dict[str, Any]]:
    """Each run of the ablation: {variant, run_id, posts: {golden id: runs.jsonl row}, scores}."""
    manifest = ablation_dir / "ablation.json"
    if not manifest.exists():
        raise BlindError(f"no ablation.json in {ablation_dir}: run `python report.py --variants <runs>` first")
    variants = []
    for run_id in json.loads(manifest.read_text())["runs"]:
        run_dir = results_dir / run_id
        meta = json.loads((run_dir / "meta.json").read_text())
        judge = config.ABLATION_JUDGES["unsupported_specifics"]
        variants.append({
            "variant": meta["variant"], "run_id": run_id,
            "posts": {row["golden_id"]: row for row in read_jsonl(run_dir / "runs.jsonl") if row.get("status") == "ok"},
            "scores": _latest(read_jsonl(run_dir / config.SCORES_FILES[judge]), judge),
        })
    return variants


def _sources_text(row: dict[str, Any]) -> list[str]:
    lines = []
    for source in row["sources"]:
        lines += [f"**{source['id']}** ({source['title'] or 'untitled'})", "", source["text"].strip(), ""]
    return lines + ["**Author profile** (the judge saw it too)", "", row["profile_text"].strip(), ""]


def _field(text: str, name: str, entry: str) -> str:
    """What was written after `name[entry]:` in a marked file."""
    line = _FIELD.format(name=name, entry=entry)
    found = re.findall(rf"^{re.escape(line)}[ \t]*(.*)$", text, flags=re.MULTILINE)
    if len(found) != 1:
        raise BlindError(f"expected one `{line}` line, found {len(found)}")
    return found[0].strip()


# ── Judge audit ───────────────────────────────────────────────────────────────

def pick_findings(variants: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    """AUDIT_FINDINGS scored unsupported_specifics findings: the AUDIT_LOWEST
    lowest scores, then a seeded random sample of the rest."""
    findings = [{"variant": v["variant"], "golden_id": golden_id, "score": row["score"], "reason": row.get("reason") or ""}
                for v in variants for (golden_id, metric), row in sorted(v["scores"].items())
                if metric == "unsupported_specifics" and row["status"] == "ok" and row.get("score") is not None
                and golden_id in v["posts"]]
    findings.sort(key=lambda f: (f["score"], f["golden_id"], f["variant"]))
    lowest, rest = findings[:config.AUDIT_LOWEST], findings[config.AUDIT_LOWEST:]
    sampled = random.Random(seed).sample(rest, min(len(rest), config.AUDIT_FINDINGS - len(lowest)))
    return lowest + sampled


def write_audit(ablation_dir: Path, variants: list[dict[str, Any]], seed: int) -> Path:
    findings = pick_findings(variants, seed)
    if not findings:
        raise BlindError("no scored unsupported_specifics findings: judge the runs with --judge-model SONNET first")
    by_variant = {v["variant"]: v for v in variants}
    lines = ["# Judge audit: unsupported_specifics", "",
             f"{len(findings)} findings: the {min(len(findings), config.AUDIT_LOWEST)} lowest scores, then a random sample. "
             "For each, read the post against the sources and decide whether the judge's score and reasoning are right. "
             f"Write `correct` or `wrong` after each `verdict[...]:`. Fewer than {config.AUDIT_MIN_CORRECT} of "
             f"{config.AUDIT_FINDINGS} correct and the report labels the metric unreliable.", ""]
    key = {}
    for number, finding in enumerate(findings, 1):
        row = by_variant[finding["variant"]]["posts"][finding["golden_id"]]
        key[f"F{number}"] = {"variant": finding["variant"], "golden_id": finding["golden_id"], "score": finding["score"]}
        lines += [f"## F{number}", "", f"Judge score: **{finding['score']:.2f}** (threshold "
                  f"{config.THRESHOLDS['unsupported_specifics']})", "", "**Judge's reasoning**", "", finding["reason"].strip(), "",
                  "**Post**", "", row["post"].strip(), "", "### Sources", "", *_sources_text(row),
                  _FIELD.format(name="verdict", entry=f"F{number}") + " ",
                  _FIELD.format(name="note", entry=f"F{number}") + " ", ""]
    (ablation_dir / "audit-key.json").write_text(json.dumps({"seed": seed, "findings": key}, indent=2) + "\n")
    path = ablation_dir / "audit.md"
    path.write_text("\n".join(lines))
    return path


def score_audit(ablation_dir: Path) -> dict[str, Any]:
    key = json.loads((ablation_dir / "audit-key.json").read_text())["findings"]
    text = (ablation_dir / "audit.md").read_text()
    marks = {}
    for finding in key:
        verdict = _field(text, "verdict", finding).lower()
        if verdict and verdict not in VERDICTS:
            raise BlindError(f"{finding}: verdict {verdict!r} is not one of {sorted(VERDICTS)}")
        if verdict:
            marks[finding] = {**key[finding], "correct": VERDICTS[verdict], "note": _field(text, "note", finding)}
    result = {"of": len(key), "marked": len(marks), "correct": sum(1 for m in marks.values() if m["correct"]), "marks": marks}
    (ablation_dir / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


# ── Blind read ────────────────────────────────────────────────────────────────

def make_read(variants: list[dict[str, Any]], goldens: dict[str, dict[str, Any]], seed: int) -> tuple[str, dict[str, Any]]:
    """(read.md, key). BLIND_GOLDENS goldens every variant returned a post for,
    chosen with the seed; under each, one post per variant in an order shuffled
    with the seed and the golden's id, labelled BLIND_LABELS."""
    if len(variants) != len(config.BLIND_LABELS):
        raise BlindError(f"the blind read takes {len(config.BLIND_LABELS)} variants, got {len(variants)}")
    shared = sorted(set.intersection(*(set(v["posts"]) for v in variants)))
    chosen = sorted(random.Random(seed).sample(shared, min(len(shared), config.BLIND_GOLDENS)))
    if not chosen:
        raise BlindError("no golden has a post from every variant")
    labels = " ".join(config.BLIND_LABELS)
    lines = ["# Blind read", "",
             f"{len(chosen)} goldens, {len(variants)} posts each, in shuffled order. After each `ranking[...]:` write the "
             f"labels best first, separated by `>` (for example `{' > '.join(config.BLIND_LABELS)}`). Use `note[...]:` for anything "
             "that decided it, and for sentences left orphaned by a deletion and posts that read flat: "
             f"name the label ({labels}).", ""]
    key: dict[str, Any] = {"seed": seed, "runs": {v["variant"]: v["run_id"] for v in variants}, "goldens": {}}
    for golden_id in chosen:
        order = list(variants)
        random.Random(f"{seed}:{golden_id}").shuffle(order)
        key["goldens"][golden_id] = {label: v["variant"] for label, v in zip(config.BLIND_LABELS, order)}
        golden = goldens[golden_id]
        lines += [f"## {golden_id}", "", f"Topic: {golden['topic']}",
                  *([f"Context: {golden['context']}"] if golden.get("context") else []), ""]
        for label, v in zip(config.BLIND_LABELS, order):
            lines += [f"### {label}", "", v["posts"][golden_id]["post"].strip(), ""]
        lines += [_FIELD.format(name="ranking", entry=golden_id) + " ", _FIELD.format(name="note", entry=golden_id) + " ", ""]
    return "\n".join(lines), key


def parse_ranking(value: str) -> list[str] | None:
    """The labels of a `ranking:` line, best first; None when the line is
    empty. Anything but each label exactly once is an error, never a guess."""
    if not value:
        return None
    labels = [token.upper() for token in re.split(r"[\s>,]+", value) if token]
    if sorted(labels) != sorted(config.BLIND_LABELS):
        raise BlindError(f"ranking {value!r} must name each of {' '.join(config.BLIND_LABELS)} exactly once")
    return labels


def score_read(read_text: str, key: dict[str, Any]) -> dict[str, Any]:
    """Join the marked read.md with its key: per variant, mean rank (1 is
    best), times ranked first and last; and every note, with the labels named."""
    ranks: dict[str, list[int]] = {variant: [] for variant in key["runs"]}
    notes, ranked = [], 0
    for golden_id, labels in key["goldens"].items():
        try:
            ranking = parse_ranking(_field(read_text, "ranking", golden_id))
        except BlindError as exc:
            raise BlindError(f"{golden_id}: {exc}") from None
        note = _field(read_text, "note", golden_id)
        if note:
            notes.append({"golden_id": golden_id, "note": note, "labels": labels})
        if ranking is None:
            continue
        ranked += 1
        for position, label in enumerate(ranking, 1):
            ranks[labels[label]].append(position)
    worst = len(config.BLIND_LABELS)
    return {"goldens": len(key["goldens"]), "ranked": ranked, "notes": notes,
            "variants": {variant: {"mean_rank": mean(given) if given else None, "first": given.count(1),
                                   "last": given.count(worst), "ranked": len(given)}
                         for variant, given in ranks.items()}}


# ── Command line ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["audit", "make", "score"])
    parser.add_argument("ablation", help="folder name in results/ablations/")
    parser.add_argument("--seed", type=int, default=config.BLIND_SEED)
    args = parser.parse_args(argv)
    ablation_dir = config.ABLATIONS_DIR / args.ablation
    try:
        if args.command == "audit":
            print(f"Wrote {write_audit(ablation_dir, load_variants(ablation_dir), args.seed)}")
        elif args.command == "make":
            from loaders import load_goldens

            text, key = make_read(load_variants(ablation_dir), {g["id"]: g for g in load_goldens()}, args.seed)
            (ablation_dir / "read.md").write_text(text)
            (ablation_dir / "key.json").write_text(json.dumps(key, indent=2) + "\n")
            print(f"Wrote {ablation_dir / 'read.md'} ({len(key['goldens'])} goldens) and key.json")
        else:
            done = False
            if (ablation_dir / "audit.md").exists():
                audit = score_audit(ablation_dir)
                print(f"Judge audit: {audit['correct']} of {audit['marked']} marked findings correct ({audit['of']} to mark)")
                done = True
            if (ablation_dir / "read.md").exists():
                blind = score_read((ablation_dir / "read.md").read_text(), json.loads((ablation_dir / "key.json").read_text()))
                (ablation_dir / "blind.json").write_text(json.dumps(blind, indent=2) + "\n")
                print(f"Blind read: {blind['ranked']} of {blind['goldens']} goldens ranked")
                for variant, stats in blind["variants"].items():
                    rank = "–" if stats["mean_rank"] is None else f"{stats['mean_rank']:.2f}"
                    print(f"  {variant:<8} mean rank {rank}  first {stats['first']}  last {stats['last']}")
                for note in blind["notes"]:
                    print(f"  {note['golden_id']}: {note['note']}  [{', '.join(f'{k}={v}' for k, v in note['labels'].items())}]")
                done = True
            if not done:
                raise BlindError(f"nothing to score in {ablation_dir}: run `audit` or `make` first")
    except BlindError as exc:
        print(f"blind.py: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
