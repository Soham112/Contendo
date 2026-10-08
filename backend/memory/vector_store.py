"""Vector store — pgvector via Supabase.

Replaces ChromaDB. All chunk storage and similarity search runs against
the `embeddings` table in Supabase using pgvector. Embeddings are still
generated locally with sentence-transformers (all-MiniLM-L6-v2, 384-dim).

Table schema (embeddings):
  id, user_id, content, embedding (vector 384), source_id, source_title,
  source_type, tags, chunk_index, total_chunks, content_hash, node_type,
  memory_context, ingested_at (timestamptz)

  memory_context values: "work" | "personal_project" | "learning" |
                         "observation" | NULL (legacy/untagged)

RPC required:
  match_embeddings(query_embedding vector, match_user_id text, match_count int)
  → table(id, content, source_id, source_title, source_type, tags,
          chunk_index, total_chunks, content_hash, node_type, memory_context,
          ingested_at, similarity float)
  See migrations/002_add_memory_context.sql for the updated RPC definition.
"""

import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from config.retrieval import RELEVANCE_THRESHOLD  # noqa: F401  (re-exported for callers)
from db.supabase_client import supabase

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# BM25 in-memory cache
# ---------------------------------------------------------------------------

BM25_CACHE_TTL_SECONDS = 300  # 5 minutes — rebuilt on cache miss or after ingest

# { user_id: {"bm25": BM25Okapi, "corpus": list[dict], "built_at": datetime} }
_bm25_cache: dict = {}

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

def init_chroma(user_id: str):
    """No-op — retained for interface compatibility. ChromaDB removed."""
    return None


def upsert_chunks(
    chunks: list[str],
    source_type: str = "",
    tags: list[str] | None = None,
    source_id: str | None = None,
    source_title: str = "",
    ingested_at: str = "",
    *,
    user_id: str,
    content_hash: str = "",
    memory_context: str | None = None,
) -> int:
    """Embed chunks locally and upsert rows into the embeddings table.

    Signature matches the call in ingestion_agent.py:
        upsert_chunks(chunks, source_type=..., tags=..., source_id=...,
                      source_title=..., ingested_at=..., user_id=...,
                      content_hash=..., memory_context=...)

    memory_context: "work" | "personal_project" | "learning" | "observation" | None

    Returns:
        Number of rows upserted.
    """
    if not chunks:
        return 0

    import uuid as _uuid
    resolved_source_id = source_id or str(_uuid.uuid4())
    resolved_tags = ",".join(tags) if tags else ""
    total = len(chunks)

    embeddings = embed_texts(chunks)

    rows = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        rows.append({
            "id": f"{resolved_source_id}_{i}",
            "user_id": user_id,
            "content": chunk,
            "embedding": embedding,
            "source_id": resolved_source_id,
            "source_title": source_title,
            "source_type": source_type,
            "tags": resolved_tags,
            "chunk_index": i,
            "total_chunks": total,
            "content_hash": content_hash,
            "node_type": "chunk",
            "memory_context": memory_context,
            "ingested_at": ingested_at or None,
        })

    supabase.table("embeddings").upsert(rows).execute()
    return len(rows)


def query_similar(
    query: str,
    user_id: str,
    n_results: int = 8,
    embedding: Optional[list[float]] = None,
) -> list[dict]:
    """Embed query locally (unless `embedding` is given) and call match_embeddings RPC.

    Returns list of dicts with keys: content, metadata (dict), similarity.
    """
    if embedding is None:
        embedding = embed_texts([query])[0]

    response = supabase.rpc("match_embeddings", {
        "query_embedding": embedding,
        "match_user_id": user_id,
        "match_count": n_results,
    }).execute()

    results = []
    for row in (response.data or []):
        content = row.get("content", "")
        results.append({
            # Flat fields — retrieval_agent accesses these directly
            # Row id. Fusion keys every hit by row id (see _chunk_key), which
            # differs from source_id_chunk_index for consolidation chunks.
            "chunk_id": row.get("id", ""),
            "text": content,
            "content": content,
            "source_id": row.get("source_id", ""),
            "source_title": row.get("source_title", ""),
            "source_type": row.get("source_type", ""),
            "tags": row.get("tags", ""),
            "chunk_index": row.get("chunk_index", 0),
            "total_chunks": row.get("total_chunks", 0),
            "content_hash": row.get("content_hash", ""),
            "node_type": row.get("node_type", "chunk"),
            "memory_context": row.get("memory_context"),  # None for legacy chunks
            "ingested_at": row.get("ingested_at", ""),
            "similarity": round(float(row.get("similarity", 0.0)), 4),
            # Nested metadata kept for any callers that use chunk["metadata"][...]
            "metadata": {
                "source_id": row.get("source_id", ""),
                "source_title": row.get("source_title", ""),
                "source_type": row.get("source_type", ""),
                "tags": row.get("tags", ""),
                "chunk_index": row.get("chunk_index", 0),
                "total_chunks": row.get("total_chunks", 0),
                "content_hash": row.get("content_hash", ""),
                "node_id": row.get("node_type", "chunk"),
                "memory_context": row.get("memory_context"),
                "ingested_at": row.get("ingested_at", ""),
            },
        })

    return results


def query_similar_batch(
    queries: list[str],
    user_id: str,
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


# ---------------------------------------------------------------------------
# BM25 helpers
# ---------------------------------------------------------------------------

# English function words, plus a few generic words ("first", "lessons") that
# matched unrelated chunks in evals. Chunks must not rank on these.
_STOP_WORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing done down during each either else even every
few first for from further get gets got had has have having he her here hers herself him himself
his how however i if in into is it its itself just last least less lesson lessons let like made make many
may me might more most much must my myself never next no nor not now of off often on once one only
or other others our ours ourselves out over own per really same say says she should since so some
still such than that the their theirs them themselves then there these they this those though
through to too under until up upon us very was way we well were what when where whether which
while who whom whose why will with within without would yet you your yours yourself yourselves
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:['’][a-z]+)?")


def _fold(token: str) -> str:
    """Possessive and plural folding: "team's" -> "team", "trails" -> "trail", "stories" -> "story"."""
    token = re.sub(r"['’]s?$", "", token)
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith(("sses", "shes", "ches", "xes", "zes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    """BM25 tokens: lowercase, punctuation stripped, stop words dropped, plurals folded."""
    tokens = []
    for raw in _TOKEN_RE.findall(text.lower()):
        token = _fold(raw)
        if len(token) > 1 and raw not in _STOP_WORDS and token not in _STOP_WORDS:
            tokens.append(token)
    return tokens


def _fetch_corpus_for_bm25(user_id: str) -> list[dict]:
    """Fetch all chunk content + metadata for a user — no embedding column.

    Deliberately excludes the 384-dim vector to minimise payload size.
    """
    response = (
        supabase.table("embeddings")
        .select(
            "id,content,source_id,source_title,source_type,"
            "tags,chunk_index,total_chunks,content_hash,node_type,memory_context,ingested_at"
        )
        .eq("user_id", user_id)
        .execute()
    )
    corpus = []
    for row in response.data or []:
        content = row.get("content", "")
        corpus.append({
            "id":             row.get("id", ""),
            "text":           content,
            "content":        content,
            "source_id":      row.get("source_id", ""),
            "source_title":   row.get("source_title", ""),
            "source_type":    row.get("source_type", ""),
            "tags":           row.get("tags", ""),
            "chunk_index":    row.get("chunk_index", 0),
            "total_chunks":   row.get("total_chunks", 0),
            "content_hash":   row.get("content_hash", ""),
            "node_type":      row.get("node_type", "chunk"),
            "memory_context": row.get("memory_context"),  # None for legacy chunks
            "ingested_at":    row.get("ingested_at", ""),
            "metadata": {
                "source_id":      row.get("source_id", ""),
                "source_title":   row.get("source_title", ""),
                "source_type":    row.get("source_type", ""),
                "tags":           row.get("tags", ""),
                "chunk_index":    row.get("chunk_index", 0),
                "total_chunks":   row.get("total_chunks", 0),
                "memory_context": row.get("memory_context"),
            },
        })
    return corpus


def _get_or_build_bm25(user_id: str) -> tuple:
    """Return (BM25Okapi, corpus) from cache, rebuilding when stale.

    Returns (None, []) when the user has no chunks yet.
    """
    now = datetime.now()
    cached = _bm25_cache.get(user_id)
    if cached and (now - cached["built_at"]).total_seconds() < BM25_CACHE_TTL_SECONDS:
        return cached["bm25"], cached["corpus"]

    corpus = _fetch_corpus_for_bm25(user_id)
    if not corpus:
        return None, []

    tokenized_corpus = [_tokenize(chunk["text"]) for chunk in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    _bm25_cache[user_id] = {"bm25": bm25, "corpus": corpus, "built_at": now}
    logger.info("BM25 index built for user %s — %d chunks", user_id, len(corpus))
    return bm25, corpus


def _bm25_upper_bound(bm25: BM25Okapi, tokens: list[str]) -> float:
    """Most a single chunk could score for these tokens: sum of idf * (k1 + 1).

    Tokens missing from the corpus count with the idf of an unseen term, so a
    query whose distinctive words the user never wrote about ("marathon")
    normalises low even if a chunk matches its generic words.
    """
    unseen_idf = math.log((bm25.corpus_size + 0.5) / 0.5)
    return sum(bm25.idf.get(t, unseen_idf) for t in tokens) * (bm25.k1 + 1)


def _query_bm25(query: str, user_id: str, n_results: int = 8) -> list[dict]:
    """Score query against full user corpus with BM25; return top-N results.

    Uses the module-level cache — cold path fetches from Supabase once,
    warm path scores in milliseconds.

    Each result carries bm25_score and bm25_norm (score / _bm25_upper_bound, 0-1).
    No similarity is set here: query_similar_hybrid fills in the real cosine.
    """
    bm25, corpus = _get_or_build_bm25(user_id)
    tokens = _tokenize(query)
    if not bm25 or not tokens:
        return []

    scores = bm25.get_scores(tokens)
    bound = _bm25_upper_bound(bm25, tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n_results]

    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            break
        result = dict(corpus[idx])
        result["bm25_score"] = float(scores[idx])
        result["bm25_norm"] = round(float(scores[idx]) / bound, 4) if bound > 0 else 0.0
        results.append(result)
    return results


def _parse_embedding(value) -> Optional[list[float]]:
    """pgvector comes back from PostgREST as a string "[0.1,...]"; tests store lists."""
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return list(value)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _fill_real_similarity(results: list[dict], query_embedding: list[float], user_id: str) -> None:
    """Give hits that only BM25 found their real cosine similarity to the query."""
    missing = [r for r in results if "similarity" not in r]
    if not missing:
        return
    ids = [_chunk_key(r) for r in missing]
    rows = (
        supabase.table("embeddings")
        .select("id,embedding")
        .eq("user_id", user_id)
        .in_("id", ids)
        .execute()
    ).data or []
    vectors = {row["id"]: _parse_embedding(row.get("embedding")) for row in rows}
    for r in missing:
        vec = vectors.get(_chunk_key(r))
        r["similarity"] = round(_cosine(query_embedding, vec), 4) if vec else 0.0


def _chunk_key(result: dict) -> str:
    """The row id. Vector hits carry it as chunk_id, BM25 and entity hits as id.

    Only legacy dicts without either fall back to source_id_chunk_index (the
    row id of a regular chunk, but not of a consolidation chunk).
    """
    return (
        result.get("chunk_id")
        or result.get("id")
        or f"{result.get('source_id')}_{result.get('chunk_index')}"
    )


def _rrf_merge(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = 60,
    n_results: int = 8,
) -> list[dict]:
    """Reciprocal Rank Fusion over vector and BM25 ranked lists.

    Chunks that rank highly in both lists rise to the top. Single-source
    chunks are included when they rank highly enough on their own.

    The vector result dict is preferred over the BM25 version for any chunk
    that appears in both lists — it carries a real cosine similarity score
    which matters for _compute_retrieval_confidence downstream. Its BM25 score
    is copied onto it. Every returned chunk gets rrf_score and rrf_rank (1-based).
    """
    combined: dict = {}  # row id → {"score": float, "result": dict}

    for rank, result in enumerate(vector_results):
        cid = _chunk_key(result)
        entry = combined.setdefault(cid, {"score": 0.0, "result": result})
        entry["score"] += 1.0 / (k + rank + 1)
        entry["result"] = result  # vector result has real similarity — keep it

    for rank, result in enumerate(bm25_results):
        cid = _chunk_key(result)
        if cid in combined:
            combined[cid]["score"] += 1.0 / (k + rank + 1)
            # Keep the vector version (it has the similarity); copy the BM25 scores onto it
            for field in ("bm25_score", "bm25_norm"):
                if field in result:
                    combined[cid]["result"][field] = result[field]
        else:
            combined[cid] = {"score": 1.0 / (k + rank + 1), "result": result}

    merged = sorted(combined.values(), key=lambda e: e["score"], reverse=True)
    top = merged[:n_results]
    for rank, entry in enumerate(top, start=1):
        entry["result"]["rrf_score"] = entry["score"]
        entry["result"]["rrf_rank"] = rank
    return [entry["result"] for entry in top]


def invalidate_bm25_cache(user_id: str) -> None:
    """Drop the cached BM25 index for a user.

    Called by ingestion_agent after new content is stored so the next
    generation request picks up the fresh corpus.
    """
    _bm25_cache.pop(user_id, None)
    logger.debug("BM25 cache invalidated for user %s", user_id)


def query_similar_hybrid(
    query: str,
    user_id: str,
    n_results: int = 8,
) -> list[dict]:
    """Hybrid search: pgvector cosine similarity + BM25 full-corpus ranking.

    Both searches run in parallel via ThreadPoolExecutor and are fused with
    Reciprocal Rank Fusion. Falls back gracefully to whichever path succeeds
    if one fails.

    BM25 uses the full user corpus (IDF computed globally — not over a
    pre-filtered subset) so rare terms like project names and specific jargon
    receive correct high weight.
    """
    vector_results: list[dict] = []
    bm25_results: list[dict] = []
    query_embedding = embed_texts([query])[0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_vector = executor.submit(query_similar, query, user_id, n_results, query_embedding)
        f_bm25   = executor.submit(_query_bm25,   query, user_id, n_results)
        try:
            vector_results = f_vector.result(timeout=10)
        except Exception as exc:
            logger.warning("vector search failed in hybrid retrieval: %s", exc)
        try:
            bm25_results = f_bm25.result(timeout=10)
        except Exception as exc:
            logger.warning("BM25 search failed in hybrid retrieval: %s", exc)

    if not vector_results and not bm25_results:
        return []
    if not bm25_results:
        merged = vector_results
    elif not vector_results:
        merged = bm25_results
    else:
        merged = _rrf_merge(vector_results, bm25_results, k=60, n_results=n_results)

    try:
        _fill_real_similarity(merged, query_embedding, user_id)
    except Exception as exc:  # never fail retrieval over this; unknown similarity counts as 0
        logger.warning("could not compute similarity for BM25-only hits: %s", exc)
        for r in merged:
            r.setdefault("similarity", 0.0)
    return merged


def query_similar_hybrid_batch(
    queries: list[str],
    user_id: str,
    n_results: int = 5,
) -> list[list[dict]]:
    """Delegates to query_similar_batch (pgvector handles ANN natively)."""
    return query_similar_batch(queries, user_id=user_id, n_results=n_results)


def query_by_hash(content_hash: str, user_id: str) -> dict | None:
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


def get_all_sources(user_id: str) -> list[dict]:
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


def delete_source(source_title: str, user_id: str) -> dict:
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


def get_chunks_by_ids(chunk_ids: list[str], user_id: str) -> list[dict]:
    """Fetch full chunk dicts for a list of chunk_ids (entity-linked retrieval).

    Returns same format as query_similar() so the retrieval pipeline can treat
    entity-linked chunks identically to vector/BM25 results.
    No similarity is set: the caller fills in the real cosine (_fill_real_similarity).
    """
    if not chunk_ids:
        return []
    response = (
        supabase.table("embeddings")
        .select(
            "id,content,source_id,source_title,source_type,"
            "tags,chunk_index,total_chunks,content_hash,node_type,memory_context,ingested_at"
        )
        .in_("id", chunk_ids)
        .eq("user_id", user_id)
        .execute()
    )
    results = []
    for row in (response.data or []):
        content = row.get("content", "")
        results.append({
            "id":            row.get("id", ""),
            "text":          content,
            "content":       content,
            "source_id":     row.get("source_id", ""),
            "source_title":  row.get("source_title", ""),
            "source_type":   row.get("source_type", ""),
            "tags":          row.get("tags", ""),
            "chunk_index":   row.get("chunk_index", 0),
            "total_chunks":  row.get("total_chunks", 0),
            "content_hash":  row.get("content_hash", ""),
            "node_type":     row.get("node_type", "chunk"),
            "memory_context": row.get("memory_context"),
            "ingested_at":   row.get("ingested_at", ""),
            "metadata": {
                "source_id":      row.get("source_id", ""),
                "source_title":   row.get("source_title", ""),
                "source_type":    row.get("source_type", ""),
                "tags":           row.get("tags", ""),
                "chunk_index":    row.get("chunk_index", 0),
                "total_chunks":   row.get("total_chunks", 0),
                "memory_context": row.get("memory_context"),
                "ingested_at":    row.get("ingested_at", ""),
            },
        })
    return results


def get_chunks_for_source(source_id: str, user_id: str) -> list[dict]:
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
    user_id: str,
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


def get_stats(user_id: str) -> dict:
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

def get_total_chunks(user_id: str) -> int:
    return get_stats(user_id)["total_chunks"]


def get_all_tags(user_id: str) -> list[str]:
    return get_stats(user_id)["tags"]
