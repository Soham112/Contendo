"""Score retrieval (docs/QUALITY.md B1) on the quality_v1 cases. No draft call.

From the repo root, with the backend venv:
    backend/venv/bin/python evals/quality_retrieval.py --name baseline            # every case
    backend/venv/bin/python evals/quality_retrieval.py --split dev --only rf-01

Runs the pipeline's own load_profile and retrieval nodes for each case, as the
case's eval user, and scores what would reach the drafter. Keyword search is
observed from here (a wrapper around the BM25 index build), so the backend is
unchanged. Writes results/quality_v1/<name>/{runs.jsonl,report.md}; persona
`me`'s per-case rows go to private/quality_v1/results/<name>/ (the repo is public).

No Claude calls and no writes besides retrieval's own stats. A case with
pillar_details runs as its own eval user, seeded with that note (quality_seed.py),
so scoring never changes a library another case reads.
"""
import env  # noqa: F401  (must be the first project import)

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import quality_fixtures as qf
import quality_metrics as qm
from guard import EnvGuardError
from loaders import EVALS_DIR, FixtureError

RESULTS_DIR = EVALS_DIR / "results" / "quality_v1"
PRIVATE_RESULTS_DIR = qf.PRIVATE_DIR / "results"


class KeywordProbe:
    """Records, per case, whether BM25 ran and how many chunks it indexed."""

    def __init__(self) -> None:
        from memory import vector_store
        self.vs, self.state = vector_store, {}
        original = vector_store._get_or_build_bm25

        def observed(user_id: str):
            try:
                bm25, corpus = original(user_id)
            except Exception as exc:
                self.state.update(ran=False, error=repr(exc))
                raise
            self.state.update(ran=bm25 is not None, corpus_size=len(corpus or []))
            return bm25, corpus

        vector_store._get_or_build_bm25 = observed

    def start(self, client: Any, user_id: str) -> None:
        count = client.table("embeddings").select("id", count="exact", head=True).eq("user_id", user_id).execute()
        self.state = {"ran": False, "error": None, "corpus_size": None, "library_chunks": count.count or 0}


def _labeller(case: dict[str, Any], snapshot: dict[str, Any] | None):
    """chunk -> label id for this case's persona."""
    from utils.business_notes import PROFILE_NOTE_TITLE
    slug = case["persona"]
    if slug == qf.ME:
        by_id = {s["source_id"]: f"me:{k}" for k, s in (snapshot or {})["labelled_sources"].items()}
    else:
        by_title = {title: label for label, title in qf.source_labels(slug).items()}
        if qf.is_business(slug):
            by_title[PROFILE_NOTE_TITLE] = slug + qf.BUSINESS_NOTE_SUFFIX

    def label(chunk: dict[str, Any], details_title: str | None) -> str:
        if (chunk.get("node_type") or "chunk") == "consolidation":
            return qm.CONSOLIDATION
        if slug == qf.ME:
            return by_id.get(chunk.get("source_id"), qm.UNLABELLED)
        title = chunk.get("source_title") or (chunk.get("metadata") or {}).get("source_title")
        if details_title and title == details_title:
            return qf.details_id(case["id"])
        return by_title.get(title, qm.UNLABELLED)
    return label


ATTEMPTS = 3  # a dropped connection is retried; the attempts are recorded


def _retrieve(case: dict[str, Any], user_id: str, client: Any, probe: KeywordProbe) -> tuple[dict, int]:
    """Run load_profile and retrieval as the pipeline does. retrieval_node turns a
    failed query into a silent fallback, so a run that didn't take the hybrid path
    is retried like a raised transport error, up to ATTEMPTS; the last one stands."""
    import httpx
    from agents.retrieval_agent import retrieval_node
    from pipeline.graph import load_profile_node

    for attempt in range(1, ATTEMPTS + 1):
        try:
            probe.start(client, user_id)
            state: dict[str, Any] = {
                "topic": case["topic"], "context": case["context"], "format": "linkedin post",
                "tone": case["tone"], "length": "standard", "quality": "standard", "user_id": user_id,
                "pillar": case["pillar"], "no_specifics": False,
            }
            load_profile_node(state)
            retrieval_node(state)
        except httpx.TransportError:
            if attempt == ATTEMPTS:
                raise
            continue
        if state.get("retrieval_path") == "hybrid" or attempt == ATTEMPTS:
            return state, attempt
    raise AssertionError("unreachable")


def run_case(case: dict[str, Any], user_id: str, client: Any, probe: KeywordProbe, snapshot) -> dict[str, Any]:
    from quality_seed import details_note_for
    details = details_note_for(case, user_id) if case["pillar_details"] else None
    state, attempts = _retrieve(case, user_id, client, probe)
    label = _labeller(case, snapshot)
    chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])
    ranked = [{"label": label(c, details and details[0]), "similarity": c.get("similarity"),
               "bm25_score": c.get("bm25_score"), "node_type": c.get("node_type") or "chunk"} for c in chunks]
    retrieved = list(dict.fromkeys(r["label"] for r in ranked))
    gate = state.get("coverage_gate") or {}
    drafted = [] if gate.get("decision") == "low_coverage" else retrieved
    own = None if case["label_confidence"] == "metadata_only" else qf.own_label_ids(case["persona"])
    return {
        "id": case["id"], "persona": case["persona"], "split": case["split"],
        "label_confidence": case["label_confidence"], "first_post": state.get("first_post"),
        "retrieval_path": state.get("retrieval_path"), "attempts": attempts,
        "gate": gate, "ranked_chunks": ranked, "drafted": drafted,
        "retrieval_timings": state.get("retrieval_timings"),
        "scores": qm.score_case(case, drafted, retrieved, own, gate.get("decision"), dict(probe.state),
                                state.get("retrieval_path"), attempts),
    }


def _cell(score: dict[str, Any], key: str) -> str:
    """One per-case cell: verdict and the value behind it."""
    s = score[key]
    verdict = s if key == "gate_accuracy" else s["pass"]
    if verdict is None:
        return "–"
    value = {
        "recall": lambda: s["at_cutoff"],
        "mrr": lambda: f"{s['value']} (rank {s['first_rank']})",
        "precision": lambda: s["value"],
        "off_topic": lambda: len(s["value"]),
        "own_share": lambda: s["value"],
        "gate_accuracy": lambda: score["gate"],
        "hybrid_reliability": lambda: f"{s.get('corpus_size')}/{s.get('library_chunks')}"
        + (f" ×{s['attempts']}" if s["attempts"] > 1 else ""),
    }[key]()
    return f"{'✓' if verdict else '✗'} {value}"


def _table(head: list[str], rows: list[list[Any]]) -> list[str]:
    fmt = lambda v: "–" if v is None else str(v)  # noqa: E731
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + [
        "| " + " | ".join(fmt(v) for v in row) + " |" for row in rows]


def _group_tables(groups: dict[str, list[dict[str, Any]]]) -> list[str]:
    groups = {name: rows for name, rows in groups.items() if rows}
    rates, means = [], []
    for name, rows in groups.items():
        scores = [r["scores"] for r in rows]
        rates.append([name, len(rows)] + [f"{p}/{n}" if n else None for p, n in qm.pass_rates(scores).values()])
        means.append([name, len(rows)] + list(qm.means(scores).values()))
    return [*_table(["Group", "n", *qm.CRITERIA], rates), "", *_table(
        ["Group", "n", *qm.means([]).keys()], means)]


def _case_table(rows: list[dict[str, Any]]) -> list[str]:
    head = ["Case", "split", *qm.CRITERIA, "drafter sources"]
    return _table(head, [[r["id"], r["split"], *(_cell(r["scores"], k) for k in qm.CRITERIA),
                          ", ".join(r["drafted"]) or "none"] for r in rows])


def write_report(rows: list[dict[str, Any]], out: Path, meta: dict[str, Any]) -> None:
    by = lambda pred: [r for r in rows if pred(r)]  # noqa: E731
    groups = {
        "dev · verified": by(lambda r: r["split"] == "dev" and r["label_confidence"] == "verified"),
        "hold-out · verified": by(lambda r: r["split"] == "holdout" and r["label_confidence"] == "verified"),
        "me · metadata_only": by(lambda r: r["label_confidence"] == "metadata_only"),
    }
    personas = {p: by(lambda r, p=p: r["persona"] == p) for p in (*qf.SYNTHETIC_SLUGS, qf.ME)}
    retried = [r["id"] for r in rows if r["attempts"] > 1]
    lines = [f"# Retrieval scorecard: {meta['name']}", "",
             f"Commit `{meta['commit']}` · {meta['at']} · eval project `{meta['project']}` · "
             f"{len(rows)} cases · Claude spend ${meta['spend']:.3f} · retried: {', '.join(retried) or 'none'}", "",
             "Criteria: docs/QUALITY.md B1. First table: cases passed / cases where the criterion applies. "
             "Second: means over applicable cases (Recall@K counts each must_use_all source and each must_use_any "
             "group as one unit; the cutoff is the sources that reach the drafter).", "",
             *_group_tables(groups), "", "## By persona", "", *_group_tables(personas), "",
             "## Cases (synthetic)", "", *_case_table([r for r in rows if r["persona"] != qf.ME]), ""]
    out.write_text("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default=datetime.now().strftime("%Y-%m-%d-retrieval"))
    parser.add_argument("--split", choices=("dev", "holdout", "all"), default="all")
    parser.add_argument("--only", action="append", help="case id (repeatable)")
    args = parser.parse_args(argv)
    try:
        users = qf.load_quality_users()
        cases = [c for c in qf.load_cases() if args.split in ("all", c["split"]) and (not args.only or c["id"] in args.only)]
        snapshot = qf.load_snapshot() if any(c["persona"] == qf.ME for c in cases) else None
        env.verify_auth_users({qf.user_slug(c): users[qf.user_slug(c)] for c in cases})
        client = env.backend_client()
        from quality_seed import UsageLog, check_spend_tracking
        check_spend_tracking(client)
    except (EnvGuardError, FixtureError) as exc:
        print(f"refusing to run: {exc}", file=sys.stderr)
        return 2
    probe = KeywordProbe()
    rows = []
    with UsageLog() as usage:
        for case in cases:
            rows.append(run_case(case, users[qf.user_slug(case)], client, probe, snapshot))
            print(f"  {case['id']}: {rows[-1]['retrieval_path']} · gate {rows[-1]['gate'].get('decision')} · "
                  f"drafter {rows[-1]['drafted'] or 'none'}")
        spend = usage.spend(client, list(users.values()))
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"name": args.name, "commit": commit, "at": usage.since, "project": env.CONFIG.project_ref,
            "spend": spend}
    out = RESULTS_DIR / args.name
    out.mkdir(parents=True, exist_ok=True)
    public = [r for r in rows if r["persona"] != qf.ME]
    (out / "runs.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in public))
    write_report(rows, out / "report.md", meta)
    me_rows = [r for r in rows if r["persona"] == qf.ME]
    if me_rows:
        private = PRIVATE_RESULTS_DIR / args.name
        private.mkdir(parents=True, exist_ok=True)
        (private / "me_runs.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in me_rows))
        (private / "me_report.md").write_text("\n".join(["# Persona me", "", *_case_table(me_rows), ""]))
    print(f"\nwrote {out.relative_to(EVALS_DIR.parent)}/report.md · spend ${meta['spend']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
