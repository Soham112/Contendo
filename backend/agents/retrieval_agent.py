import logging

from pipeline.state import PipelineState
from memory.vector_store import (
    RELEVANCE_THRESHOLD,
    get_adjacent_chunks,
    query_similar,
    query_similar_hybrid,
)
from memory.hierarchy_store import get_source_node, get_topic_node
from memory.retrieval_stats_store import increment_retrieval

logger = logging.getLogger(__name__)


def infer_seniority_level(profile: dict) -> str:
    """Infer the user's career seniority as 'junior', 'mid', or 'senior'.

    Checks `years_of_experience` field first. Falls back to role title keyword
    matching. Defaults to 'mid' when nothing matches.
    """
    years = profile.get("years_of_experience")
    if years is not None:
        try:
            y = int(years)
            if y <= 3:
                return "junior"
            elif y <= 10:
                return "mid"
            else:
                return "senior"
        except (TypeError, ValueError):
            pass

    role = (profile.get("role") or "").lower()

    senior_keywords = [
        "senior", "lead", "principal", "director", "vp", "head of",
        "staff", "distinguished", "fellow", "cto", "ceo", "founder",
    ]
    junior_keywords = [
        "junior", "intern", "associate", "student", "graduate", "entry", "jr",
    ]
    for kw in senior_keywords:
        if kw in role:
            return "senior"
    for kw in junior_keywords:
        if kw in role:
            return "junior"

    return "mid"


def resolve_attribution_frames(chunks: list[dict], profile: dict) -> str:
    """Assign an explicit writing frame to each retrieved chunk individually.

    Phase 1 fix: frame is assigned per-chunk, not per-cluster. The old
    cluster-level assignment caused a single personal_note to contaminate
    all other chunks in its tag cluster with a PERSONAL frame, leading to
    first-person hallucinations about article/video content.

    Frame resolution per chunk (strict priority):
    1. memory_context field (Phase 1 — most reliable signal):
         "work"             → PERSONAL_WORK
         "personal_project" → PERSONAL_PROJECT
         "learning"         → LEARNING (never PERSONAL, even if source_type=personal_note)
         "observation"      → OBSERVATION
    2. source_type fallback (for legacy chunks where memory_context is None):
         "personal_note"    → PERSONAL
         others             → EXPERT_OUTSIDER if tags overlap with profile expertise,
                              else LEARNING calibrated by seniority

    Output: structured labeled block for direct prompt injection.
    """
    if not chunks:
        return "No relevant knowledge base entries found. Draw on general expertise."

    seniority = infer_seniority_level(profile)
    topics_of_expertise = [t.lower().strip() for t in profile.get("topics_of_expertise", [])]

    def _get_field(chunk: dict, flat_key: str) -> str:
        """Read a field from a flat chunk dict or its nested 'metadata' sub-dict."""
        val = chunk.get(flat_key)
        if val is not None:
            return str(val)
        return str(chunk.get("metadata", {}).get(flat_key) or "")

    # ── Step 1: Per-chunk frame assignment ──────────────────────────────────
    def _chunk_frame(chunk: dict, tags: set[str]) -> str:
        memory_context = chunk.get("memory_context") or chunk.get("metadata", {}).get("memory_context")

        # Primary signal: memory_context (set at ingest time — most reliable)
        if memory_context == "work":
            return "PERSONAL_WORK"
        if memory_context == "personal_project":
            return "PERSONAL_PROJECT"
        if memory_context == "observation":
            return "OBSERVATION"
        if memory_context == "learning":
            # Explicitly marked as external knowledge — never PERSONAL
            in_expertise = any(
                any(exp in tag or tag in exp for exp in topics_of_expertise)
                for tag in tags
            ) if topics_of_expertise and tags else False
            return "EXPERT_OUTSIDER" if in_expertise else f"LEARNING_{seniority.upper()}"

        # Fallback: legacy chunks without memory_context — use source_type heuristic
        source_type = _get_field(chunk, "source_type")
        if source_type == "personal_note":
            return "PERSONAL"

        in_expertise = any(
            any(exp in tag or tag in exp for exp in topics_of_expertise)
            for tag in tags
        ) if topics_of_expertise and tags else False
        return "EXPERT_OUTSIDER" if in_expertise else f"LEARNING_{seniority.upper()}"

    chunk_tags: list[set[str]] = []
    chunk_frames: list[str] = []
    for chunk in chunks:
        raw_tags = _get_field(chunk, "tags")
        tags = {t.strip().lower() for t in raw_tags.split(",") if t.strip()} if raw_tags else set()
        chunk_tags.append(tags)
        chunk_frames.append(_chunk_frame(chunk, tags))

    # ── Step 2: Build labeled output block grouped by frame ─────────────────
    frame_order = [
        "PERSONAL_WORK",
        "PERSONAL_PROJECT",
        "PERSONAL",
        "OBSERVATION",
        "EXPERT_OUTSIDER",
        "LEARNING_SENIOR",
        "LEARNING_MID",
        "LEARNING_JUNIOR",
    ]
    frame_headers = {
        "PERSONAL_WORK": (
            "PERSONAL EXPERIENCE — WORK CONTEXT — write in first person, "
            "this is something you built or did professionally:"
        ),
        "PERSONAL_PROJECT": (
            "PERSONAL EXPERIENCE — PERSONAL PROJECT — write in first person, "
            "this is your own side project or experiment:"
        ),
        "PERSONAL": (
            "PERSONAL EXPERIENCE — write these claims in first person:"
        ),
        "OBSERVATION": (
            "OBSERVATION — patterns you've noticed in the world, "
            "write with 'I've noticed' or 'I keep seeing', not as personal lived experience:"
        ),
        "EXPERT_OUTSIDER": (
            "EXPERT OUTSIDER PERSPECTIVE — you know adjacent territory deeply,\n"
            "this is newer to you, write with authority but honest curiosity:"
        ),
        "LEARNING_SENIOR": "LEARNING — confident framing at senior level, not passive:",
        "LEARNING_MID":    "LEARNING — confident framing at mid level, not passive:",
        "LEARNING_JUNIOR": "LEARNING — confident framing at junior level, not passive:",
    }

    frame_to_chunk_indices: dict[str, list[int]] = {}
    for idx, frame in enumerate(chunk_frames):
        frame_to_chunk_indices.setdefault(frame, []).append(idx)

    lines: list[str] = []
    for frame in frame_order:
        if frame not in frame_to_chunk_indices:
            continue
        lines.append(frame_headers[frame])
        for chunk_idx in frame_to_chunk_indices[frame]:
            chunk = chunks[chunk_idx]
            source_type = _get_field(chunk, "source_type") or "article"
            tag_list = ", ".join(sorted(chunk_tags[chunk_idx])) if chunk_tags[chunk_idx] else "none"
            text = _get_field(chunk, "text") or _get_field(chunk, "content")
            lines.append(f"[source: {source_type} | tags: {tag_list}]")
            lines.append(text)
            lines.append("")

    return "\n".join(lines).strip()


def _compute_retrieval_confidence(results: list[dict]) -> str:
    """Classify retrieval coverage based on unfiltered raw retrieval results.

    vector_store currently returns `similarity` (higher is better), not `distance`.
    Threshold mapping from cosine distance to similarity:
    - distance < 0.55  <=>  similarity > 0.45  (strong match)
    - distance < 0.70  <=>  similarity > 0.30  (any match)
    """
    if not results:
        return "low"

    high_quality = [r for r in results if float(r.get("similarity", 0.0)) > 0.45]
    any_quality = [r for r in results if float(r.get("similarity", 0.0)) > 0.30]

    if len(high_quality) >= 3:
        return "high"
    if len(high_quality) >= 1 or len(any_quality) >= 3:
        return "medium"
    return "low"


def _build_retrieval_bundle(chunks: list[dict], user_id: str) -> dict:
    """Enrich flat chunk list with source and topic context from hierarchy_store.

    For each unique source_id: fetch source summary + sibling chunks (top 3 sources only).
    Falls back gracefully if hierarchy_store has no data for a source (pre-migration).
    """
    bundle: dict = {
        "chunks": chunks,
        "source_contexts": {},
        "topic_contexts": [],
    }

    # Collect unique source_ids in similarity order; first 3 get sibling fetching
    seen_source_ids: dict[str, int] = {}  # source_id -> index of first matching chunk
    for i, chunk in enumerate(chunks):
        sid = chunk.get("source_id", "")
        if sid and sid not in seen_source_ids:
            seen_source_ids[sid] = i

    top_3_source_ids = list(seen_source_ids.keys())[:3]
    seen_topic_ids: set[str] = set()

    for sid, first_chunk_idx in seen_source_ids.items():
        source_node = None
        try:
            source_node = get_source_node(sid, user_id=user_id)
        except Exception:
            pass

        sibling_chunks: list[str] = []
        if sid in top_3_source_ids:
            try:
                matched_chunk_index = chunks[first_chunk_idx].get("chunk_index", 0)
                sibling_chunks = get_adjacent_chunks(
                    sid, matched_chunk_index, user_id=user_id, window=1
                )
            except Exception:
                sibling_chunks = []

        if source_node:
            bundle["source_contexts"][sid] = {
                "source_title": source_node.get("source_title") or "",
                "source_type": source_node.get("source_type") or "",
                "source_summary": source_node.get("source_summary") or "",
                "sibling_chunks": sibling_chunks,
            }
            topic_id = source_node.get("topic_id") or ""
            if topic_id and topic_id not in seen_topic_ids:
                seen_topic_ids.add(topic_id)
                try:
                    topic_node = get_topic_node(topic_id, user_id=user_id)
                    if topic_node:
                        bundle["topic_contexts"].append({
                            "topic_label": topic_node.get("topic_label") or "",
                            "topic_summary": topic_node.get("topic_summary") or "",
                        })
                except Exception:
                    pass
        else:
            # Source not yet in hierarchy_store (pre-migration): use chunk metadata as fallback
            matched_chunk = chunks[first_chunk_idx]
            bundle["source_contexts"][sid] = {
                "source_title": "",
                "source_type": matched_chunk.get("source_type") or "",
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


def retrieval_node(state: PipelineState) -> PipelineState:
    topic = state["topic"]
    context = state.get("context", "")
    user_id = state.get("user_id", "default")

    query = f"{topic}. {context}" if context else topic

    bundle: dict = {"chunks": [], "source_contexts": {}, "topic_contexts": []}
    raw_results: list[dict] = []
    try:
        logger.info(f"Hybrid retrieval used for user {user_id}, topic: {topic[:50]}")
        raw_results = query_similar_hybrid(query, user_id=user_id, n_results=8)
        chunks = [
            r for r in raw_results
            if float(r.get("similarity", 0.0)) >= RELEVANCE_THRESHOLD
        ]
        bundle = _build_retrieval_bundle(chunks, user_id)
        state["retrieval_bundle"] = bundle
        state["retrieved_context"] = _format_retrieved_context(bundle)

        # Track retrieval stats — never let this break retrieval
        try:
            seen_titles: set[str] = set()
            for chunk in bundle["chunks"]:
                title = chunk.get("source_title", "").strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    increment_retrieval(user_id, title)
        except Exception as stat_err:
            print(f"[retrieval_node] stat tracking failed (non-fatal): {stat_err}")
    except Exception as e:
        print(f"[retrieval_node] hierarchical retrieval failed ({e}), falling back to flat")
        try:
            raw_results = query_similar(query, n_results=8, user_id=user_id)
            chunks = [
                r for r in raw_results
                if float(r.get("similarity", 0.0)) >= RELEVANCE_THRESHOLD
            ]
            bundle = {"chunks": chunks, "source_contexts": {}, "topic_contexts": []}
        except Exception:
            raw_results = []
            bundle = {"chunks": [], "source_contexts": {}, "topic_contexts": []}
        state["retrieval_bundle"] = bundle
        state["retrieved_context"] = ""

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
    state["retrieval_confidence"] = _compute_retrieval_confidence(raw_results)
    state["retrieved_chunk_count"] = len(retrieved_texts)

    # Debug: print a sample so attribution labels can be verified at runtime.
    if retrieved_texts:
        print(f"[retrieval_node] {len(retrieved_texts)} chunks retrieved. Sample: {retrieved_texts[0][:120]!r}")

    return state
