"""Vector store — pgvector via Supabase.

Replaces ChromaDB. All chunk storage and similarity search runs against
the `embeddings` table in Supabase using pgvector. Embeddings are still
generated locally with sentence-transformers (all-MiniLM-L6-v2, 384-dim).

Table schema (embeddings):
  id, user_id, content, embedding (vector 384), source_id, source_title,
  source_type, tags, chunk_index, total_chunks, content_hash, node_type,
  ingested_at (timestamptz)

RPC required:
  match_embeddings(query_embedding vector, match_user_id text, match_count int)
  → table(id, content, source_id, source_title, source_type, tags,
          chunk_index, total_chunks, content_hash, node_type, ingested_at,
          similarity float)
"""

import logging
from typing import Optional

from sentence_transformers import SentenceTransformer

from db.supabase_client import supabase

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RELEVANCE_THRESHOLD = 0.3

_embedder: Optional[SentenceTransformer] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Encode texts locally; returns list of 384-dim float vectors."""
    embedder = _get_embedder()
    return embedder.encode(texts, show_progress_bar=False).tolist()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_chroma(user_id: str = "default"):
    """No-op — retained for interface compatibility. ChromaDB removed."""
    return None


def upsert_chunks(
    chunks: list[str],
    metadatas: list[dict],
    ids: list[str],
    user_id: str = "default",
) -> int:
    """Embed chunks locally and upsert rows into the embeddings table.

    Args:
        chunks:    List of text strings to embed and store.
        metadatas: Parallel list of metadata dicts (one per chunk).
        ids:       Parallel list of unique row IDs (one per chunk).
        user_id:   Supabase user ID used for data isolation.

    Returns:
        Number of rows upserted.
    """
    if not chunks:
        return 0

    embeddings = embed_texts(chunks)

    rows = []
    for chunk, meta, chunk_id, embedding in zip(chunks, metadatas, ids, embeddings):
        rows.append({
            "id": chunk_id,
            "user_id": user_id,
            "content": chunk,
            "embedding": embedding,
            "source_id": meta.get("source_id", ""),
            "source_title": meta.get("source_title", ""),
            "source_type": meta.get("source_type", ""),
            "tags": meta.get("tags", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "total_chunks": meta.get("total_chunks", len(chunks)),
            "content_hash": meta.get("content_hash", ""),
            "node_type": meta.get("node_type", "chunk"),
        })

    supabase.table("embeddings").upsert(rows).execute()
    return len(rows)


def query_similar(
    query: str,
    user_id: str = "default",
    n_results: int = 8,
) -> list[dict]:
    """Embed query locally and call match_embeddings RPC.

    Returns list of dicts with keys: content, metadata (dict), similarity.
    """
    embedding = embed_texts([query])[0]

    response = supabase.rpc("match_embeddings", {
        "query_embedding": embedding,
        "match_user_id": user_id,
        "match_count": n_results,
    }).execute()

    results = []
    for row in (response.data or []):
        results.append({
            "content": row.get("content", ""),
            "metadata": {
                "source_id": row.get("source_id", ""),
                "source_title": row.get("source_title", ""),
                "source_type": row.get("source_type", ""),
                "tags": row.get("tags", ""),
                "chunk_index": row.get("chunk_index", 0),
                "total_chunks": row.get("total_chunks", 0),
                "content_hash": row.get("content_hash", ""),
                "node_type": row.get("node_type", "chunk"),
                "ingested_at": row.get("ingested_at", ""),
            },
            "similarity": round(float(row.get("similarity", 0.0)), 4),
        })

    return results


def query_similar_batch(
    queries: list[str],
    user_id: str = "default",
    n_results: int = 8,
) -> list[list[dict]]:
    """Embed all queries in one batch forward pass, then query each via RPC.

    Returns list[list[dict]] — one result list per query, same format as
    query_similar().
    """
    if not queries:
        return []

    # Single batched encoder forward pass for efficiency
    embeddings = embed_texts(queries)

    results = []
    for query in queries:
        results.append(query_similar(query, user_id=user_id, n_results=n_results))

    return results


def query_similar_hybrid(
    query: str,
    user_id: str = "default",
    n_results: int = 8,
) -> list[dict]:
    """Delegates to query_similar (pgvector handles ANN natively)."""
    return query_similar(query, user_id=user_id, n_results=n_results)


def query_similar_hybrid_batch(
    queries: list[str],
    user_id: str = "default",
    n_results: int = 5,
) -> list[list[dict]]:
    """Delegates to query_similar_batch (pgvector handles ANN natively)."""
    return query_similar_batch(queries, user_id=user_id, n_results=n_results)


def query_by_hash(content_hash: str, user_id: str = "default") -> dict | None:
    """Check if content with this hash already exists.

    Returns {"chunk_count": int, "tags": list[str]} if found, None otherwise.
    """
    response = (
        supabase.table("embeddings")
        .select("content,tags")
        .eq("content_hash", content_hash)
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return None

    tags_raw = rows[0].get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    return {"chunk_count": len(rows), "tags": tags}


def get_all_sources(user_id: str = "default") -> list[dict]:
    """Return all sources for the user, grouped by source_id, sorted newest first."""
    response = (
        supabase.table("embeddings")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return []

    groups: dict[str, dict] = {}
    for row in rows:
        sid = row.get("source_id") or "unknown"
        if sid not in groups:
            groups[sid] = {
                "source_id": sid,
                "source_title": row.get("source_title") or "Untitled",
                "source_type": row.get("source_type", "unknown"),
                "ingested_at": row.get("ingested_at", ""),
                "chunk_count": 0,
                "tag_set": set(),
            }
        groups[sid]["chunk_count"] += 1
        raw_tags = row.get("tags", "")
        if raw_tags:
            for tag in raw_tags.split(","):
                tag = tag.strip()
                if tag:
                    groups[sid]["tag_set"].add(tag)

    sources = []
    for entry in groups.values():
        sources.append({
            "source_id": entry["source_id"],
            "source_title": entry["source_title"],
            "source_type": entry["source_type"],
            "ingested_at": entry["ingested_at"],
            "chunk_count": entry["chunk_count"],
            "tags": sorted(entry["tag_set"]),
        })

    sources.sort(key=lambda s: s["ingested_at"] or "", reverse=True)
    return sources


def delete_source(source_title: str, user_id: str = "default") -> dict:
    """Delete all chunks with matching source_title for this user.

    Returns {"deleted": True, "chunks_removed": int}.
    """
    # Fetch matching rows first to get a count
    count_resp = (
        supabase.table("embeddings")
        .select("id")
        .eq("source_title", source_title)
        .eq("user_id", user_id)
        .execute()
    )
    count = len(count_resp.data or [])

    if count > 0:
        supabase.table("embeddings").delete().eq("source_title", source_title).eq("user_id", user_id).execute()

    return {"deleted": True, "chunks_removed": count}


def get_chunks_for_source(source_id: str, user_id: str = "default") -> list[dict]:
    """Return all chunks for a source_id, sorted by chunk_index ascending.

    Each dict: {"text": str, "chunk_index": int, "source_id": str}
    """
    response = (
        supabase.table("embeddings")
        .select("content,chunk_index,source_id")
        .eq("source_id", source_id)
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []

    chunks = [
        {
            "text": row.get("content", ""),
            "chunk_index": int(row.get("chunk_index", 0)),
            "source_id": source_id,
        }
        for row in rows
    ]
    chunks.sort(key=lambda c: c["chunk_index"])
    return chunks


def get_adjacent_chunks(
    source_id: str,
    chunk_index: int,
    user_id: str = "default",
    window: int = 1,
) -> list[str]:
    """Return texts of chunks adjacent to chunk_index within the same source.

    Fetches indices [chunk_index-window .. chunk_index+window], excluding
    chunk_index itself. Returns texts in ascending index order.
    """
    lo = max(0, chunk_index - window)
    hi = chunk_index + window

    response = (
        supabase.table("embeddings")
        .select("content,chunk_index")
        .eq("source_id", source_id)
        .eq("user_id", user_id)
        .gte("chunk_index", lo)
        .lte("chunk_index", hi)
        .execute()
    )
    rows = response.data or []

    adjacent = [
        (int(row["chunk_index"]), row.get("content", ""))
        for row in rows
        if int(row.get("chunk_index", -1)) != chunk_index
    ]
    adjacent.sort(key=lambda t: t[0])
    return [text for _, text in adjacent]


def get_stats(user_id: str = "default") -> dict:
    """Return total chunk count and unique tags for the user.

    Returns {"total_chunks": int, "tags": list[str]}.
    """
    response = (
        supabase.table("embeddings")
        .select("tags")
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []

    tag_set: set[str] = set()
    for row in rows:
        raw = row.get("tags", "")
        if raw:
            for tag in raw.split(","):
                tag = tag.strip()
                if tag:
                    tag_set.add(tag)

    return {"total_chunks": len(rows), "tags": sorted(tag_set)}


# ---------------------------------------------------------------------------
# Legacy aliases — kept so any remaining callers don't break at import time
# ---------------------------------------------------------------------------

def get_total_chunks(user_id: str = "default") -> int:
    return get_stats(user_id)["total_chunks"]


def get_all_tags(user_id: str = "default") -> list[str]:
    return get_stats(user_id)["tags"]
