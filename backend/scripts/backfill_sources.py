"""Backfill `sources` (migration 014) for sources stored before originals were kept.

Each source is rebuilt from its stored chunks (utils.source_rebuild) and marked
origin_status = 'rebuilt_from_chunks'; authorship and title_origin stay NULL.
Consolidation rows are derived data, not sources, and are skipped.

    cd backend
    venv/bin/python -m scripts.backfill_sources --target eval              # report only (read-only)
    venv/bin/python -m scripts.backfill_sources --target eval --apply
    venv/bin/python -m scripts.backfill_sources --target production        # report only
    venv/bin/python -m scripts.backfill_sources --target production --apply --confirm-production

The report lists per-user counts, the rebuild_check and hash-match
distribution, and duplicate content (two sources of one user with the same
content_hash) to resolve before migration 015. Source ids only, no titles or text.
Re-running --apply skips sources that already have a row.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils.source_rebuild import CHUNKER_VERSION, content_hash_for, rebuild_source

PAGE = 1000  # PostgREST's maximum rows per request
CHUNK_COLUMNS = ("user_id,source_id,content,chunk_index,total_chunks,content_hash,"
                 "source_title,source_type,node_type,ingested_at")
# source_type values that name the input path exactly; everything else is 'unknown'
# ('article' covers both URL scrapes and file uploads, 'note' both typed text and Obsidian).
EXACT_INPUT_TYPES = {"youtube": "youtube", "image": "image", "business_profile": "business_profile"}


def fetch_chunk_rows(client: Any) -> list[dict]:
    """Every chunk row of every user, paged past the 1,000-row response limit."""
    rows: list[dict] = []
    while True:
        page = (client.table("embeddings").select(CHUNK_COLUMNS).order("id")
                .range(len(rows), len(rows) + PAGE - 1).execute().data or [])
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def fetch_source_ids(client: Any) -> set[str]:
    ids: list[dict] = []
    while True:
        page = (client.table("sources").select("source_id").order("source_id")
                .range(len(ids), len(ids) + PAGE - 1).execute().data or [])
        ids.extend(page)
        if len(page) < PAGE:
            return {r["source_id"] for r in ids}


def _is_source_chunk(row: dict) -> bool:
    if row.get("node_type") is None:
        return row.get("source_type") != "consolidation"
    return row["node_type"] == "chunk"


def plan(rows: list[dict]) -> list[dict]:
    """The sources rows to write, one per (user_id, source_id) of source chunks."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        if _is_source_chunk(row) and row.get("source_id"):
            groups[(row["user_id"], row["source_id"])].append(row)
    planned = []
    for (user_id, source_id), chunks in sorted(groups.items()):
        rebuilt = rebuild_source(chunks)
        first = min(chunks, key=lambda c: c.get("chunk_index") or 0)
        ingested_at = min((c["ingested_at"] for c in chunks if c.get("ingested_at")), default=None)
        row = {
            "source_id": source_id,
            "user_id": user_id,
            "status": "ready",
            "input_type": EXACT_INPUT_TYPES.get(first.get("source_type") or "", "unknown"),
            "title": first.get("source_title"),
            "extracted_text": rebuilt.text,
            "extractor": "rebuilt_from_chunks",
            "extractor_version": CHUNKER_VERSION,
            "content_hash": content_hash_for(chunks, rebuilt.text),
            "origin_status": "rebuilt_from_chunks",
            "rebuild_check": rebuilt.check,
            "rebuild_hash_match": rebuilt.hash_match,
        }
        if ingested_at:
            row |= {"extracted_at": ingested_at, "created_at": ingested_at}
        planned.append(row)
    return planned


def duplicates(planned: list[dict]) -> dict[str, list[list[str]]]:
    """Per user: groups of source ids that share one content_hash."""
    by_hash: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in planned:
        by_hash[(row["user_id"], row["content_hash"])].append(row["source_id"])
    out: dict[str, list[list[str]]] = defaultdict(list)
    for (user_id, _), ids in sorted(by_hash.items()):
        if len(ids) > 1:
            out[user_id].append(sorted(ids))
    return dict(out)


def report(rows: list[dict], planned: list[dict], existing: set[str]) -> str:
    skipped = Counter("no source_id" if not r.get("source_id") else "derived (consolidation)"
                      for r in rows if not (_is_source_chunk(r) and r.get("source_id")))
    lines = [f"chunk rows read: {len(rows)}; sources planned: {len(planned)}; "
             f"already in sources: {sum(r['source_id'] in existing for r in planned)}"]
    lines += [f"  rows skipped, {k}: {v}" for k, v in sorted(skipped.items())]
    lines.append("per user (sources, chunks):")
    chunks_per_user = Counter(r["user_id"] for r in rows if _is_source_chunk(r) and r.get("source_id"))
    for user_id, n in sorted(Counter(r["user_id"] for r in planned).items()):
        lines.append(f"  {user_id}: {n} sources, {chunks_per_user[user_id]} chunks")
    lines.append("rebuild_check x content_hash match:")
    for (check, match), n in sorted(Counter((r["rebuild_check"], str(r["rebuild_hash_match"]))
                                            for r in planned).items()):
        lines.append(f"  {check:17} hash_match={match:5}: {n}")
    lines.append("input_type: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(r["input_type"] for r in planned).items())))
    dups = duplicates(planned)
    lines.append(f"duplicate content (resolve before migration 015): {sum(len(g) for g in dups.values())} groups")
    for user_id, groups in dups.items():
        for ids in groups:
            lines.append(f"  {user_id}: {', '.join(ids)}")
    return "\n".join(lines)


def apply(client: Any, planned: list[dict], existing: set[str]) -> int:
    new = [r for r in planned if r["source_id"] not in existing]
    for start in range(0, len(new), 100):
        client.table("sources").insert(new[start:start + 100]).execute()
    return len(new)


def _client(target: str) -> Any:
    """Load the target's environment, then the backend's client (import order matters)."""
    if target == "eval":
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evals"))
        import env  # noqa: F401  (guard: refuses anything but the eval project)
        return env.backend_client()
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from db.supabase_client import supabase
    return supabase


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", choices=("eval", "production"), required=True)
    parser.add_argument("--apply", action="store_true", help="write the planned rows (default: report only)")
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and args.target == "production" and not args.confirm_production:
        parser.error("--apply on production needs --confirm-production")

    client = _client(args.target)
    rows = fetch_chunk_rows(client)
    planned = plan(rows)
    existing = fetch_source_ids(client)
    print(report(rows, planned, existing))
    if args.apply:
        print(f"inserted {apply(client, planned, existing)} sources rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
