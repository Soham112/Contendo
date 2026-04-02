from pipeline.state import PipelineState
from memory.vector_store import get_adjacent_chunks, query_similar
from memory.hierarchy_store import get_source_node, get_topic_node
from memory.retrieval_stats_store import increment_retrieval


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
    try:
        chunks = query_similar(query, top_k=8, user_id=user_id)
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
            chunks = query_similar(query, top_k=8, user_id=user_id)
            bundle = {"chunks": chunks, "source_contexts": {}, "topic_contexts": []}
        except Exception:
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

    # Debug: print a sample so attribution labels can be verified at runtime.
    if retrieved_texts:
        print(f"[retrieval_node] {len(retrieved_texts)} chunks retrieved. Sample: {retrieved_texts[0][:120]!r}")

    return state
