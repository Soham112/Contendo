#!/usr/bin/env python3
"""
Migrate existing ChromaDB chunks into the hierarchy_store.

For each source already in ChromaDB, this script:
  1. Reconstructs the full source text from its chunks (sorted by chunk_index).
  2. Generates a 2-3 sentence source summary via Claude Haiku.
  3. Assigns the source to an existing topic (2+ shared tags) or creates a new one.
  4. Writes a source_node and topic_node to backend/data/hierarchy.db.

The script is idempotent — by default it skips sources already in hierarchy_store.
Use --force to re-process and overwrite existing entries.
Use --dry_run to preview without writing anything.

Usage (from project root, with backend venv active):
    python scripts/migrate_hierarchy.py
    python scripts/migrate_hierarchy.py --user_id default
    python scripts/migrate_hierarchy.py --dry_run
    python scripts/migrate_hierarchy.py --force
"""

import argparse
import os
import sys
import uuid
from pathlib import Path

# Add backend/ to sys.path so we can import from memory.*, agents.*, etc.
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

import anthropic

from memory.vector_store import get_collection
from memory.hierarchy_store import (
    add_source_to_topic,
    find_matching_topic,
    init_db,
    source_node_exists,
    upsert_source_node,
    upsert_topic_node,
)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            max_retries=3,
        )
    return _client


def _generate_summary(text: str) -> str:
    """Generate a 2-3 sentence summary via Claude Haiku. Returns "" on failure."""
    preview = " ".join(text.split()[:700])
    try:
        msg = _get_client().messages.create(
            model=HAIKU_MODEL,
            max_tokens=120,
            system=(
                "You are a summarization assistant. Summarize the provided text in "
                "2-3 concise sentences that capture the key ideas. Return only the "
                "summary, no preamble."
            ),
            messages=[{"role": "user", "content": f"Summarize this:\n\n{preview}"}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"    [warn] summary generation failed: {e}")
        return ""


def _assign_topic(
    source_id: str,
    tags: list[str],
    user_id: str,
    dry_run: bool,
) -> str:
    """Assign source to an existing topic or create a new one. Returns topic_id."""
    existing = find_matching_topic(tags, user_id=user_id)
    if existing:
        topic_id = existing["topic_id"]
        if not dry_run:
            add_source_to_topic(topic_id, source_id, user_id=user_id)
        return topic_id

    topic_id = str(uuid.uuid4())
    topic_label = tags[0] if tags else "general"
    if not dry_run:
        upsert_topic_node(
            topic_id=topic_id,
            user_id=user_id,
            topic_label=topic_label,
            topic_summary="",
            representative_tags=tags,
            child_source_ids=[source_id],
        )
    return topic_id


def migrate(user_id: str = "default", dry_run: bool = False, force: bool = False) -> None:
    init_db()

    collection = get_collection(user_id)
    total_count = collection.count()
    if total_count == 0:
        print(f"Collection contendo_{user_id} is empty. Nothing to migrate.")
        return

    print(f"Loading all chunks from contendo_{user_id} ({total_count} total chunks)...")
    results = collection.get(include=["documents", "metadatas"])

    # Group chunks by source_id, collecting all metadata for each source
    sources: dict[str, dict] = {}
    for doc, meta in zip(results["documents"], results["metadatas"]):
        sid = meta.get("source_id", "")
        if not sid:
            continue  # skip chunks without source_id (shouldn't happen, but be safe)
        if sid not in sources:
            sources[sid] = {
                "source_id": sid,
                "source_title": meta.get("source_title") or "",
                "source_type": meta.get("source_type") or "article",
                "ingested_at": meta.get("ingested_at") or "",
                "tags_raw": meta.get("tags") or "",
                "chunks": [],
            }
        sources[sid]["chunks"].append({
            "text": doc,
            "chunk_index": int(meta.get("chunk_index", 0)),
        })

    total_sources = len(sources)
    print(f"Found {total_sources} unique sources.\n")

    if dry_run:
        print("[dry_run] No data will be written.\n")

    processed = 0
    skipped = 0
    errors = 0

    for i, (sid, source_data) in enumerate(sources.items(), 1):
        title_preview = (source_data["source_title"] or sid[:12])[:60]
        print(f"Processing {i}/{total_sources}: {title_preview!r} ...")

        if not force and source_node_exists(sid, user_id=user_id):
            print(f"  [skip] already in hierarchy_store")
            skipped += 1
            continue

        # Reconstruct full source text from chunks sorted by chunk_index
        sorted_chunks = sorted(source_data["chunks"], key=lambda c: c["chunk_index"])
        full_text = " ".join(c["text"] for c in sorted_chunks)
        tags = [t.strip() for t in source_data["tags_raw"].split(",") if t.strip()]

        if dry_run:
            print(f"  [dry_run] would generate summary and assign topic")
            print(f"  tags: {tags[:6]!r}")
            print(f"  chunks: {len(sorted_chunks)}")
            processed += 1
            continue

        try:
            summary = _generate_summary(full_text)
            topic_id = _assign_topic(sid, tags, user_id=user_id, dry_run=False)
            upsert_source_node(
                source_id=sid,
                user_id=user_id,
                source_title=source_data["source_title"],
                source_type=source_data["source_type"],
                ingested_at=source_data["ingested_at"],
                tags=tags,
                total_chunks=len(sorted_chunks),
                topic_id=topic_id,
                source_summary=summary,
            )
            print(f"  [ok] summary written, topic: {topic_id[:8]}...")
            processed += 1
        except Exception as e:
            print(f"  [error] {e}")
            errors += 1

    print(f"\n{'─' * 50}")
    print(f"Done.")
    print(f"  Processed : {processed}")
    print(f"  Skipped   : {skipped} (already in hierarchy_store)")
    print(f"  Errors    : {errors}")
    print(f"  Total     : {total_sources}")
    if dry_run:
        print("\n(dry_run — no data was written)")
    elif processed > 0:
        print(f"\nRun verification:")
        print(f"  sqlite3 backend/data/hierarchy.db 'SELECT COUNT(*) FROM source_nodes;'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate ChromaDB chunks to hierarchy_store (source + topic nodes)."
    )
    parser.add_argument(
        "--user_id",
        default="default",
        help="User collection to migrate (default: 'default')",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Preview without writing to hierarchy_store",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-process sources already in hierarchy_store (overwrites)",
    )
    args = parser.parse_args()

    migrate(user_id=args.user_id, dry_run=args.dry_run, force=args.force)
