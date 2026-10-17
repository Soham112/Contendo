import logging

from config import retrieval as cfg
from config import features
from pipeline.state import PipelineState
from memory.vector_store import (
    _chunk_key,
    _fill_real_similarity,
    embed_texts,
    get_adjacent_chunks,
    get_chunks_by_ids,
    query_similar,
    query_similar_hybrid,
)
from memory.hierarchy_store import get_source_nodes, get_topic_nodes
from pipeline.trace import timed
from memory.retrieval_stats_store import record_retrievals_in_background
from utils.frames import chunk_field, chunk_frame, chunk_tags, infer_seniority_level  # noqa: F401  (re-exported)

logger = logging.getLogger(__name__)


def _top_scores(results: list[dict]) -> tuple[float, float]:
    """(top-1 real cosine, top-1 normalized BM25) over raw retrieval results."""
    top_cosine = max((float(r.get("similarity") or 0.0) for r in results), default=0.0)
    top_bm25 = max((float(r.get("bm25_norm") or 0.0) for r in results), default=0.0)
    return top_cosine, top_bm25


def _is_relevant(chunk: dict) -> bool:
    """Use a chunk when its own cosine or its own normalized BM25 is strong enough."""
    return (
        float(chunk.get("similarity") or 0.0) >= cfg.RELEVANCE_THRESHOLD
        or float(chunk.get("bm25_norm") or 0.0) >= cfg.STRONG_BM25
    )


def _has_coverage(top_cosine: float, top_bm25: float) -> bool:
    return top_cosine >= cfg.COVERAGE_MIN_COSINE or top_bm25 >= cfg.COVERAGE_MIN_BM25


def _compute_retrieval_confidence(results: list[dict]) -> str:
    """Classify coverage from the best real cosine and the best normalized BM25 score.

    high:   top-1 cosine >= HIGH_CONFIDENCE_COSINE
    medium: the coverage gate passes (top-1 cosine or top-1 BM25 strong enough)
    low:    neither (the coverage gate blocks drafting)
    """
    top_cosine, top_bm25 = _top_scores(results)
    if top_cosine >= cfg.HIGH_CONFIDENCE_COSINE:
        return "high"
    if _has_coverage(top_cosine, top_bm25):
        return "medium"
    return "low"


def coverage_gate(results: list[dict], bypass: bool = False, first_post: bool = False, business: dict | None = None) -> dict:
    """Decide whether the knowledge base covers the topic well enough to draft.

    decision: "pass"; "low_coverage"; "bypassed" (low coverage, but the request
    asked for a no-specifics post); or "skipped_first_post" (low coverage, but
    a user's first post is written from their profile and onboarding answers,
    not the knowledge base). Includes the scores, thresholds, and the closest
    sources found, for the response and the generation trace. With the business
    block enabled, insufficient coverage is profile_only when the pillar is
    writable_from_profile (or absent); other pillars remain low_coverage even
    on a first post. Passing numeric coverage is checked before that fallback.
    """
    top_cosine, top_bm25 = _top_scores(results)
    covered = _has_coverage(top_cosine, top_bm25)
    if covered:
        decision = "pass"
    elif business is not None and features.business_block_enabled():
        pillar = business.get("pillar") or {}
        decision = "profile_only" if not pillar or pillar["writable_from_profile"] else "low_coverage"
    elif bypass:
        decision = "bypassed"
    elif first_post:
        decision = "skipped_first_post"
    else:
        decision = "low_coverage"
    closest = sorted(results, key=lambda r: float(r.get("similarity") or 0.0), reverse=True)
    closest_sources, seen = [], set()
    for r in closest:
        title = r.get("source_title") or ""
        if title in seen:
            continue
        seen.add(title)
        closest_sources.append({
            "title": title,
            "preview": (r.get("text") or r.get("content") or "")[:200],
            "similarity": round(float(r.get("similarity") or 0.0), 3),
        })
        if len(closest_sources) == cfg.CLOSEST_SOURCES:
            break
    return {
        "decision": decision,
        "top_cosine": round(top_cosine, 4),
        "top_bm25_norm": round(top_bm25, 4),
        "min_cosine": cfg.COVERAGE_MIN_COSINE,
        "min_bm25_norm": cfg.COVERAGE_MIN_BM25,
        "closest_sources": closest_sources,
    }


def _build_retrieval_bundle(chunks: list[dict], user_id: str) -> dict:
    """Enrich flat chunk list with source and topic context from hierarchy_store.

    For each unique source_id: source summary, plus sibling chunks for the top 3
    sources. One query each for source nodes, sibling chunks and topic nodes.
    Falls back gracefully if hierarchy_store has no data for a source (pre-migration).
    """
    bundle: dict = {
        "chunks": chunks,
        "source_contexts": {},
        "topic_contexts": [],
    }

    # Unique source_ids in similarity order; the first 3 get sibling chunks
    seen_source_ids: dict[str, int] = {}  # source_id -> index of first matching chunk
    for i, chunk in enumerate(chunks):
        sid = chunk.get("source_id", "")
        if sid and sid not in seen_source_ids:
            seen_source_ids[sid] = i

    source_nodes: dict[str, dict] = {}
    try:
        source_nodes = get_source_nodes(list(seen_source_ids), user_id=user_id)
    except Exception as exc:
        logger.warning("source node lookup failed: %s", exc)

    siblings: dict[str, list[str]] = {}
    top_3 = list(seen_source_ids.items())[:3]
    try:
        siblings = get_adjacent_chunks(
            {sid: chunks[idx].get("chunk_index", 0) for sid, idx in top_3},
            user_id=user_id, window=1,
        )
    except Exception as exc:
        logger.warning("sibling chunk lookup failed: %s", exc)

    # Topics in order of the first source that names them
    topic_ids = list(dict.fromkeys(
        node.get("topic_id") for sid in seen_source_ids
        if (node := source_nodes.get(sid)) and node.get("topic_id")
    ))
    topic_nodes: dict[str, dict] = {}
    try:
        topic_nodes = get_topic_nodes(topic_ids, user_id=user_id)
    except Exception as exc:
        logger.warning("topic node lookup failed: %s", exc)
    for tid in topic_ids:
        if topic_node := topic_nodes.get(tid):
            bundle["topic_contexts"].append({
                "topic_label": topic_node.get("topic_label") or "",
                "topic_summary": topic_node.get("topic_summary") or "",
            })

    for sid, first_chunk_idx in seen_source_ids.items():
        source_node = source_nodes.get(sid)
        sibling_chunks = siblings.get(sid, [])
        if source_node:
            bundle["source_contexts"][sid] = {
                "source_title": source_node.get("source_title") or "",
                "source_type": source_node.get("source_type") or "",
                "source_summary": source_node.get("source_summary") or "",
                "sibling_chunks": sibling_chunks,
            }
        else:
            # Source not yet in hierarchy_store (pre-migration): use chunk metadata as fallback
            bundle["source_contexts"][sid] = {
                "source_title": "",
                "source_type": chunks[first_chunk_idx].get("source_type") or "",
                "source_summary": "",
                "sibling_chunks": sibling_chunks,
            }

    return bundle


def _format_retrieved_context(bundle: dict) -> str:
    """Produce a structured text block for prompt injection.

    Returns "" when no source has a summary/title (pre-migration state), which
    triggers the flat-chunk fallback in draft_agent — safe and backward compatible.

    Top 3 unique sources get: title + summary + matched chunk + 1 sibling.
    Sources 4+ get: flat chunk with [source_type: X] label only.
    """
    chunks = bundle.get("chunks", [])
    source_contexts = bundle.get("source_contexts", {})
    topic_contexts = bundle.get("topic_contexts", [])

    if not chunks:
        return ""

    # Only emit enriched format when at least one source has a summary or title
    has_any_enrichment = any(
        ctx.get("source_summary") or ctx.get("source_title")
        for ctx in source_contexts.values()
    )
    if not has_any_enrichment:
        return ""

    lines: list[str] = []

    # Topic context — only when a non-empty topic_summary exists
    for tc in topic_contexts[:3]:
        label = tc.get("topic_label") or ""
        summary = tc.get("topic_summary") or ""
        if label and summary:
            lines.append("=== TOPIC CONTEXT ===")
            lines.append(f"Topic: {label}")
            lines.append(f"  {summary[:200]}")
            lines.append("")
            break  # one topic block is enough

    lines.append("=== KNOWLEDGE BASE ===")

    # Top 3 unique source_ids in similarity order
    top_3_sids: list[str] = list(dict.fromkeys(
        c.get("source_id", "") for c in chunks if c.get("source_id")
    ))[:3]
    enriched_sources_seen: set[str] = set()

    for i, chunk in enumerate(chunks):
        sid = chunk.get("source_id", "")
        source_type = chunk.get("source_type") or "article"
        if source_type == "unknown":
            source_type = "article"

        # [source_type: X] label is always present — satisfies attribution safety rules
        attr_label = f"[source_type: {source_type}]"

        use_enriched = sid in top_3_sids and sid not in enriched_sources_seen
        if use_enriched:
            enriched_sources_seen.add(sid)
            ctx = source_contexts.get(sid, {})
            title = ctx.get("source_title") or ""
            summary = ctx.get("source_summary") or ""
            siblings = ctx.get("sibling_chunks") or []

            lines.append(f"[Chunk {i + 1}] {attr_label}")
            if title:
                lines.append(f"Source: {title}")
            if summary:
                lines.append(f"Summary: {summary[:300]}")
            lines.append(chunk["text"])
            if siblings:
                # Include first sibling only, capped to avoid token bloat
                lines.append(f"[Adjacent context]: {siblings[0][:400]}")
        else:
            # Flat format for lower-ranked sources — same as current system
            lines.append(f"[Chunk {i + 1}] {attr_label} {chunk['text']}")

        lines.append("")  # blank separator

    return "\n".join(lines).strip()


def _get_entity_ids_for_query(query_topic: str, user_id: str) -> list[str]:
    """Find entity_ids for entities mentioned in the query topic text.

    Simple string match — fast, no LLM call. Returns [] on any failure.
    Skips entities shorter than 3 characters to avoid false matches.
    """
    try:
        from memory.entity_store import get_entities_for_user, _normalize_entity_name
        entities = get_entities_for_user(user_id)
        query_normalized = _normalize_entity_name(query_topic)
        return [
            e["entity_id"]
            for e in entities
            if len(e.get("entity_name", "")) >= 3
            and e["entity_name"] in query_normalized  # entity_names already stored normalized
        ]
    except Exception as exc:
        logger.debug("entity query matching failed: %s", exc)
        return []


def _enrich_with_entity_chunks(
    existing_chunks: list[dict],
    query_topic: str,
    user_id: str,
    max_additional: int = 4,
) -> list[dict]:
    """Add entity-linked chunks not already in existing_chunks (up to max_additional).

    Total retrieval budget after enrichment: len(existing_chunks) + max_additional (≤ 12).
    Entity-linked chunks are tagged with entity_linked=True, given their real
    cosine similarity to the query, and the closest ones are kept. They are
    never counted by retrieval confidence or the coverage gate, which only use
    chunks that matched the query directly.
    Returns existing_chunks unchanged on any failure.
    """
    try:
        entity_ids = _get_entity_ids_for_query(query_topic, user_id)
        if not entity_ids:
            return existing_chunks

        existing_ids = {_chunk_key(c) for c in existing_chunks}

        from memory.entity_store import get_chunk_ids_for_entity
        candidate_ids: list[str] = []
        seen: set[str] = set()
        for eid in entity_ids:
            for cid in get_chunk_ids_for_entity(eid, user_id):
                if cid not in existing_ids and cid not in seen:
                    candidate_ids.append(cid)
                    seen.add(cid)

        if not candidate_ids:
            return existing_chunks

        additional = get_chunks_by_ids(candidate_ids if features.business_block_enabled() else candidate_ids[: max_additional * 2], user_id)
        for chunk in additional:
            chunk["entity_linked"] = True
        _fill_real_similarity(additional, embed_texts([query_topic])[0], user_id)
        additional.sort(key=lambda c: c.get("similarity", 0.0), reverse=True)

        added = additional[:max_additional]
        logger.info(
            "entity enrichment: +%d chunks for user %s (query: %s)",
            len(added), user_id, query_topic[:50],
        )
        return existing_chunks + added
    except Exception as exc:
        logger.warning("entity chunk enrichment failed: %s", exc)
        return existing_chunks


def retrieval_node(state: PipelineState) -> PipelineState:
    topic = state["topic"]
    context = state.get("context", "")
    user_id = state["user_id"]

    query = f"{topic}. {context}" if context else topic
    state["retrieval_query"] = query
    # Wall time of each part, {step, seconds} (pipeline.trace.timed).
    timings: list[dict] = []
    state["retrieval_timings"] = timings

    # Load experience nodes once: the fact checker reads the entity names from state
    experience_nodes: list[dict] = []
    try:
        from memory.experience_store import get_experience_nodes
        with timed(timings, "experience_nodes"):
            experience_nodes = get_experience_nodes(user_id)
    except Exception as exc:
        logger.debug("experience_nodes load failed (non-fatal): %s", exc)
    state["experience_nodes"] = experience_nodes

    bundle: dict = {"chunks": [], "source_contexts": {}, "topic_contexts": []}
    raw_results: list[dict] = []
    try:
        # STOPGAP: topic excerpts are logged. Proper fix: fix/retrieval-failure-status
        # replaces content logging with request IDs, categories and counts.
        logger.info(f"Hybrid retrieval used for user {user_id}, topic: {topic[:50]}")
        with timed(timings, "hybrid_search"):
            raw_results = query_similar_hybrid(query, user_id=user_id, n_results=8)
        chunks = [r for r in raw_results if _is_relevant(r)]
        # Phase 4: enrich with entity-linked chunks not in top-8 (up to 4 additional, total ≤ 12)
        with timed(timings, "entity_enrichment"):
            chunks = _enrich_with_entity_chunks(chunks, query_topic=query, user_id=user_id, max_additional=4)
        with timed(timings, "source_context"):
            bundle = _build_retrieval_bundle(chunks, user_id)
        state["retrieval_bundle"] = bundle
        state["retrieved_context"] = _format_retrieved_context(bundle)
        state["retrieval_path"] = "hybrid"

        # Retrieval stats are written off the request path; never let them break retrieval
        try:
            with timed(timings, "retrieval_stats"):
                record_retrievals_in_background(
                    user_id, [chunk.get("source_id", "") for chunk in bundle["chunks"]]
                )
        except Exception as stat_err:
            logger.warning("retrieval stat tracking failed (non-fatal): %s", stat_err)
    except Exception as e:
        print(f"[retrieval_node] hierarchical retrieval failed ({e}), falling back to flat")
        try:
            raw_results = query_similar(query, n_results=8, user_id=user_id)
            chunks = [r for r in raw_results if _is_relevant(r)]
            bundle = {"chunks": chunks, "source_contexts": {}, "topic_contexts": []}
        except Exception:
            # STOPGAP: a failed fallback query becomes empty results and low coverage.
            # Proper fix: fix/retrieval-failure-status records retrieval errors and
            # returns an explicit failure instead of treating memory as empty.
            raw_results = []
            bundle = {"chunks": [], "source_contexts": {}, "topic_contexts": []}
        state["retrieval_bundle"] = bundle
        state["retrieved_context"] = ""
        state["retrieval_path"] = "flat_fallback"

    # ALWAYS set retrieved_chunks — backward compat (critic_agent and others read this)
    retrieved_texts = []
    for chunk in bundle["chunks"]:
        source_type = chunk.get("source_type", "") or "article"
        # Default unknown/missing source_type to "article" — safe assumption that
        # content came from an external source rather than the user's own notes.
        if source_type == "unknown":
            source_type = "article"
        retrieved_texts.append(f"[source_type: {source_type}] {chunk['text']}")

    state["retrieved_chunks"] = retrieved_texts
    state["has_chunks"] = bool(bundle["chunks"])
    # Confidence and the gate use raw_results only: chunks that matched the
    # query directly, never entity-linked additions.
    state["retrieval_confidence"] = _compute_retrieval_confidence(raw_results)
    state["retrieved_chunk_count"] = len(retrieved_texts)
    state["coverage_gate"] = coverage_gate(
        raw_results,
        bypass=bool(state.get("no_specifics")),
        first_post=bool(state.get("first_post")),
        business=state.get("business"),
    )
    logger.info(
        "coverage gate: %s (top cosine %.3f, top bm25 %.3f) for user %s",
        state["coverage_gate"]["decision"], state["coverage_gate"]["top_cosine"],
        state["coverage_gate"]["top_bm25_norm"], user_id,
    )

    # STOPGAP: source excerpts are logged. Proper fix: fix/retrieval-failure-status
    # removes source content from logs and records only request IDs/counts.
    # Debug: print a sample so attribution labels can be verified at runtime.
    if retrieved_texts:
        print(f"[retrieval_node] {len(retrieved_texts)} chunks retrieved. Sample: {retrieved_texts[0][:120]!r}")

    return state
