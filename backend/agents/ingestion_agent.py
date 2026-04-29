import anthropic
import hashlib
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from dotenv import load_dotenv

from memory.vector_store import invalidate_bm25_cache, query_by_hash, upsert_chunks
from memory.hierarchy_store import (
    add_source_to_topic,
    find_matching_topic,
    source_node_exists,
    upsert_source_node,
    upsert_topic_node,
)
from memory.entity_store import upsert_entity, upsert_chunk_entities, _normalize_entity_name
from utils.chunker import chunk_text

load_dotenv()

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

TAG_SYSTEM_PROMPT = """You are a tag extraction assistant. Given a passage of text, extract 3–8 short, lowercase topic tags that best describe what this content is about.

Rules:
- Tags must be 1–3 words each
- Use specific, meaningful terms (e.g. "machine learning", "product strategy", "ux research")
- Avoid generic tags like "article", "text", "content", "post"
- Return ONLY a JSON array of strings, nothing else

Example output: ["machine learning", "transformer models", "ai inference", "scaling laws"]"""

CONTEXT_CLASSIFY_SYSTEM_PROMPT = """You are a context classifier. Given a short passage of text, determine which of four memory contexts it belongs to.

Contexts:
- "work"             — professional work: team projects, client work, production systems, sprints, company context
- "personal_project" — personal side projects, experiments, weekend builds, indie work
- "learning"         — external knowledge: articles, research, books, courses, videos, things the user read or watched
- "observation"      — patterns the user has noticed, meta-commentary, "I keep seeing", "most teams I talk to"

Key signals:
- "we built", "our team", "the client", "production", "sprint", "my company" → work
- "I built", "my side project", "I was experimenting", "over the weekend", "my own" → personal_project
- "the article argues", "research shows", "according to", "I read", "the author", "studies show" → learning
- "I keep seeing", "I've noticed", "the pattern I notice", "most teams", "in my experience observing" → observation

Return ONLY one of: "work", "personal_project", "learning", "observation"
No explanation, no punctuation, just the single label."""

ENTITY_EXTRACT_SYSTEM_PROMPT = """You are an entity extraction assistant. Extract named entities from the provided text.

Entity types (use exactly these strings):
- "technology"   — languages, frameworks, tools, platforms, libraries
- "company"      — organisations, employers, clients, products, startups
- "project"      — named codebases, products, initiatives, features
- "concept"      — abstract ideas, principles, paradigms
- "methodology"  — processes, frameworks, workflows (e.g. "Agile", "OKRs")
- "market"       — industries, verticals, customer segments
- "metric"       — quantitative measures (e.g. "ARR", "p99 latency", "MAU")
- "person"       — named individuals

Relationship types (use exactly these strings):
- "mentions"       — referenced in passing
- "explains"       — described or taught in depth
- "used_in"        — used or applied in the context
- "contrasts_with" — compared against or argued against

Rules:
- Extract only specific named entities — skip generic words like "software" or "team".
- Maximum 10 entities per chunk. Prefer the most specific and meaningful ones.
- entity_name must be the canonical form (e.g. "React" not "React.js", "PostgreSQL" not "postgres").
- Return ONLY a JSON array, no preamble, no markdown.

Example output:
[
  {"entity_name": "React", "entity_type": "technology", "relationship_type": "used_in"},
  {"entity_name": "Stripe", "entity_type": "company", "relationship_type": "mentions"},
  {"entity_name": "OKRs", "entity_type": "methodology", "relationship_type": "explains"}
]"""

SUMMARY_MODEL = "claude-haiku-4-5-20251001"


def compute_content_hash(content: str) -> str:
    normalised = content.strip().lower()
    return hashlib.sha256(normalised.encode()).hexdigest()


def _extract_tags(text: str) -> list[str]:
    # Use first 1500 words for tag extraction to keep costs low
    preview = " ".join(text.split()[:1500])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": f"Extract topic tags from this text:\n\n{preview}",
            }
        ],
        system=TAG_SYSTEM_PROMPT,
    )
    raw = message.content[0].text.strip()

    try:
        tags = json.loads(raw)
        if isinstance(tags, list):
            return [str(t).lower().strip() for t in tags if t]
    except json.JSONDecodeError:
        pass

    # Fallback: split on commas if JSON parse failed
    return [t.strip().strip('"[]').lower() for t in raw.split(",") if t.strip()]


def _generate_source_summary(content: str) -> str:
    """Generate a 2-3 sentence summary of the source via Claude Haiku.

    Uses first 700 words of content. Returns "" on any failure — never
    blocks ingestion.
    """
    preview = " ".join(content.split()[:700])
    try:
        message = client.messages.create(
            model=SUMMARY_MODEL,
            max_tokens=120,
            system="You are a summarization assistant. Summarize the provided text in 2-3 concise sentences that capture the key ideas. Return only the summary, no preamble.",
            messages=[{"role": "user", "content": f"Summarize this:\n\n{preview}"}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.warning("source summary generation failed: %s", e)
        return ""


VALID_MEMORY_CONTEXTS = {"work", "personal_project", "learning", "observation"}


def _classify_memory_context(text: str) -> str:
    """Classify text into a memory context using Claude Haiku language pattern detection.

    Uses first 200 words. Returns one of: "work" | "personal_project" |
    "learning" | "observation". Defaults to "learning" on any failure.

    Called at ingest time when the user has not explicitly set memory_context,
    and also via the /suggest-memory-context endpoint for UI pre-selection.
    """
    preview = " ".join(text.split()[:200])
    try:
        message = client.messages.create(
            model=SUMMARY_MODEL,
            max_tokens=10,
            system=CONTEXT_CLASSIFY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": preview}],
        )
        result = message.content[0].text.strip().lower().strip('"\'')
        if result in VALID_MEMORY_CONTEXTS:
            return result
    except Exception as e:
        logger.warning("memory context classification failed: %s", e)
    return "learning"


def _extract_entities_for_chunk(chunk_text: str) -> list[dict]:
    """Extract named entities from a single chunk via Claude Haiku.

    Returns list of dicts: [{entity_name, entity_type, relationship_type}].
    Returns [] on any failure — never blocks ingestion.
    """
    try:
        message = client.messages.create(
            model=SUMMARY_MODEL,
            max_tokens=300,
            system=ENTITY_EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Extract entities from:\n\n{chunk_text}"}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        entities = json.loads(raw)
        if isinstance(entities, list):
            return [
                e for e in entities
                if isinstance(e, dict)
                and e.get("entity_name")
                and e.get("entity_type")
                and e.get("relationship_type")
            ]
    except Exception as e:
        logger.debug("entity extraction failed for chunk: %s", e)
    return []


def _store_entities_for_chunks(
    chunks: list[str],
    source_id: str,
    user_id: str,
) -> list[str]:
    """Extract entities for all chunks in parallel and persist to entity tables.

    Runs Haiku calls concurrently (one per chunk) via ThreadPoolExecutor.
    All failures are caught and logged — never blocks ingestion.
    chunk_id format mirrors upsert_chunks: f"{source_id}_{chunk_index}"

    Returns the deduplicated list of entity names that were successfully stored.
    Used by the consolidation trigger to check which entities crossed the threshold.
    """
    stored_entity_names: list[str] = []
    names_lock = __import__("threading").Lock()

    def process_chunk(index: int, text: str) -> None:
        chunk_id = f"{source_id}_{index}"
        raw_entities = _extract_entities_for_chunk(text)
        if not raw_entities:
            return
        resolved: list[dict] = []
        for e in raw_entities:
            try:
                eid = upsert_entity(
                    user_id=user_id,
                    entity_name=e["entity_name"],
                    entity_type=e["entity_type"],
                )
                resolved.append({"entity_id": eid, "relationship_type": e["relationship_type"]})
                with names_lock:
                    stored_entity_names.append(e["entity_name"])
            except Exception as exc:
                logger.debug("entity upsert failed: %s — %s", e["entity_name"], exc)
        upsert_chunk_entities(chunk_id, user_id, resolved)

    max_workers = min(len(chunks), 5)  # cap at 5 concurrent Haiku calls
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_chunk, i, text): i
            for i, text in enumerate(chunks)
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.warning("entity storage failed for chunk %d: %s", futures[future], e)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_names: list[str] = []
    for name in stored_entity_names:
        if name not in seen:
            seen.add(name)
            unique_names.append(name)
    return unique_names


def _crossref_experience_context(text: str, user_id: str) -> str | None:
    """Check if text mentions known experience entities and return a suggested context.

    Loads experience_nodes for the user and checks if any entity_name appears
    in the text. If a work node matches → "work". If a personal_project node
    matches → "personal_project". Returns None when no match found, so the
    caller can fall back to the Haiku classifier.

    Designed to be fast: one DB read + string matching, no LLM call.
    """
    try:
        from memory.experience_store import get_experience_nodes
        nodes = get_experience_nodes(user_id)
        if not nodes:
            return None
        text_lower = text.lower()
        work_match = False
        project_match = False
        for node in nodes:
            name = _normalize_entity_name(node.get("entity_name", ""))
            if not name or len(name) < 3:
                continue
            if name in text_lower:
                if node["node_type"] == "work":
                    work_match = True
                elif node["node_type"] == "personal_project":
                    project_match = True
        # work takes precedence over personal_project when both match
        if work_match:
            return "work"
        if project_match:
            return "personal_project"
    except Exception as e:
        logger.debug("experience cross-reference failed: %s", e)
    return None


def _assign_to_topic(source_id: str, tags: list[str], user_id: str) -> str:
    """Assign source to an existing topic (2+ tag overlap) or create a new one.

    Returns the topic_id assigned.
    """
    existing_topic = find_matching_topic(tags, user_id=user_id)
    if existing_topic:
        topic_id = existing_topic["topic_id"]
        add_source_to_topic(topic_id, source_id, user_id=user_id)
        return topic_id

    # No matching topic — create one with the first tag as the label
    topic_id = str(uuid.uuid4())
    topic_label = tags[0] if tags else "general"
    upsert_topic_node(
        topic_id=topic_id,
        user_id=user_id,
        topic_label=topic_label,
        topic_summary="",
        representative_tags=tags,
        child_source_ids=[source_id],
    )
    return topic_id


def ingest_content(
    content: str,
    source_type: str,
    source_title: str | None = None,
    user_id: str = "default",
    memory_context: str | None = None,
) -> dict:
    """Ingest content into the knowledge base.

    memory_context: "work" | "personal_project" | "learning" | "observation" | None
        When None, the Haiku language pattern classifier is run to infer context
        automatically. Explicitly provided values are always used as-is.

    Returns dict with keys: chunks_stored, tags, suggested_context (when inferred).
    """
    chunks = chunk_text(content)
    if not chunks:
        return {"chunks_stored": 0, "tags": []}

    # Deduplication check — skip Claude call entirely if content already exists
    content_hash = compute_content_hash(content)
    existing = query_by_hash(content_hash, user_id=user_id)
    if existing:
        return {
            "chunks_stored": existing["chunk_count"],
            "tags": existing["tags"],
            "duplicate": True,
        }

    tags = _extract_tags(content)

    # Infer memory_context when not explicitly provided.
    # Priority: experience cross-reference (deterministic) → Haiku classifier (LLM).
    # Store the suggestion so the caller can surface it in the response.
    context_was_inferred = False
    if memory_context is None:
        crossref = _crossref_experience_context(content, user_id)
        if crossref:
            memory_context = crossref
            logger.info("memory_context inferred via experience cross-ref: %s", memory_context)
        else:
            memory_context = _classify_memory_context(content)
        context_was_inferred = True
    elif memory_context not in VALID_MEMORY_CONTEXTS:
        logger.warning("invalid memory_context %r — falling back to classifier", memory_context)
        crossref = _crossref_experience_context(content, user_id)
        memory_context = crossref or _classify_memory_context(content)
        context_was_inferred = True

    if source_title is None:
        # Derive a human-readable title from the first 80 chars of content
        first_line = content.strip().splitlines()[0].strip()
        source_title = (first_line[:80] + "…") if len(first_line) > 80 else first_line

    ingested_at = datetime.now(timezone.utc).isoformat()

    # Generate source_id here so it's accessible for hierarchy persistence
    source_id = str(uuid.uuid4())

    stored = upsert_chunks(
        chunks,
        source_type=source_type,
        tags=tags,
        source_id=source_id,
        source_title=source_title,
        ingested_at=ingested_at,
        user_id=user_id,
        content_hash=content_hash,
        memory_context=memory_context,
    )

    # Invalidate BM25 cache so the next generation request picks up the new
    # corpus. Safe to call even if no cache entry exists yet.
    invalidate_bm25_cache(user_id)

    # Entity extraction — runs per chunk after successful storage.
    # Wrapped in try/except: a failure here must NEVER fail ingestion.
    extracted_entity_names: list[str] = []
    try:
        extracted_entity_names = _store_entities_for_chunks(
            chunks, source_id=source_id, user_id=user_id
        )
    except Exception as e:
        logger.warning("entity extraction failed for source %s: %s", source_id, e)

    # Memory consolidation — check if any extracted entities have crossed the
    # 3-source threshold and synthesise a consolidation chunk for them.
    # Runs after entity extraction. Failures must NEVER fail ingestion.
    if extracted_entity_names:
        try:
            from agents.consolidation_agent import maybe_consolidate_entities
            maybe_consolidate_entities(extracted_entity_names, user_id=user_id)
        except Exception as e:
            logger.warning("consolidation trigger failed for source %s: %s", source_id, e)

    # Hierarchy persistence — runs after successful chunk storage.
    # Wrapped in try/except: a failure here must NEVER fail ingestion.
    try:
        if not source_node_exists(source_id, user_id=user_id):
            source_summary = _generate_source_summary(content)
            topic_id = _assign_to_topic(source_id, tags, user_id=user_id)
            upsert_source_node(
                source_id=source_id,
                user_id=user_id,
                source_title=source_title,
                source_type=source_type,
                ingested_at=ingested_at,
                tags=tags,
                total_chunks=stored,
                topic_id=topic_id,
                source_summary=source_summary,
            )
    except Exception as e:
        logger.warning("hierarchy persistence failed for source %s: %s", source_id, e)

    result: dict = {"chunks_stored": stored, "tags": tags, "memory_context": memory_context}
    if context_was_inferred:
        result["suggested_context"] = memory_context
    return result
