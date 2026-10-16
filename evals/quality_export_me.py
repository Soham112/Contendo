"""Export persona `me` (Soham's production library) to a local file. Read-only.

    backend/venv/bin/python evals/quality_export_me.py

Reads production through a client that can only select, and writes
private/quality_v1/me/export.json (gitignored: the repo is public). It never
imports backend code and never touches the eval project: quality_seed.py
--import-me loads the file into the eval project afterwards.

The production user is the owner of the labelled sources in
private/quality_v1/me/snapshot.json, so no user id is stored in the repo.
Rows are copied as they are today, flaws included (missing memory_context,
mislabels, chunks longer than the embedder's window): the baseline measures
today's ingestion. Their provenance is recorded as copied_from_production_chunks;
after step 3 these sources can only be rebuilt from chunks, never re-extracted.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

EVALS_DIR = Path(__file__).resolve().parent
BACKEND_ENV = EVALS_DIR.parent / "backend" / ".env"
PRIVATE_DIR = EVALS_DIR / "private" / "quality_v1" / "me"
SNAPSHOT_FILE = PRIVATE_DIR / "snapshot.json"
EXPORT_FILE = PRIVATE_DIR / "export.json"
PAGE = 1000  # Supabase returns at most 1,000 rows per request

# (table, columns, user column). Posts keep only what retrieval reads (the
# topic list decides first_post); post content is not copied.
TABLES = (
    ("embeddings", "*", "user_id"),
    ("entities", "*", "user_id"),
    ("chunk_entities", "*", "user_id"),
    ("experience_nodes", "*", "user_id"),
    ("profiles", "id,data", "id"),
    ("accounts", "*", "user_id"),
    ("posts", "topic,format,tone,archetype,created_at", "user_id"),
)


class ReadOnlyClient:
    """Production access that can only page through a select."""

    def __init__(self, url: str, key: str):
        from supabase import create_client
        self._client = create_client(url, key)

    def select_all(self, table: str, columns: str, column: str, value: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        while True:
            page = (self._client.table(table).select(columns).eq(column, value)
                    .range(len(rows), len(rows) + PAGE - 1).execute().data or [])
            rows += page
            if len(page) < PAGE:
                return rows

    def owner_of(self, source_ids: list[str]) -> str:
        rows = self._client.table("embeddings").select("user_id").in_("source_id", source_ids).execute().data or []
        owners = {r["user_id"] for r in rows}
        if len(owners) != 1:
            raise SystemExit(f"labelled sources belong to {len(owners)} users, expected exactly one")
        return owners.pop()


def main() -> int:
    snapshot = json.loads(SNAPSHOT_FILE.read_text())
    prod = dotenv_values(BACKEND_ENV)  # read into a dict only; os.environ is untouched
    url, key = prod.get("SUPABASE_URL"), prod.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print(f"refusing: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing from {BACKEND_ENV}", file=sys.stderr)
        return 2
    eval_url = dotenv_values(EVALS_DIR / ".env").get("EVAL_SUPABASE_URL")
    if url == eval_url:
        print("refusing: backend/.env points at the eval project, not production", file=sys.stderr)
        return 2
    client = ReadOnlyClient(url, key)
    labelled = [s["source_id"] for s in snapshot["labelled_sources"].values()]
    owner = client.owner_of(labelled)
    data = {table: client.select_all(table, cols, col, owner) for table, cols, col in TABLES}
    found = {r["source_id"] for r in data["embeddings"]}
    missing = [sid for sid in labelled if sid not in found]
    if missing:
        print(f"refusing: labelled sources not in the export: {missing}", file=sys.stderr)
        return 2
    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "provenance": "copied_from_production_chunks",
        "counts": {t: len(rows) for t, rows in data.items()},
        "tables": data,
    }
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_FILE.write_text(json.dumps(export, ensure_ascii=False) + "\n")
    sources = len({r["source_id"] for r in data["embeddings"]})
    print(f"exported {sources} sources: " + ", ".join(f"{t} {n}" for t, n in export["counts"].items()))
    print(f"wrote {EXPORT_FILE.relative_to(EVALS_DIR.parent)} (gitignored)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
