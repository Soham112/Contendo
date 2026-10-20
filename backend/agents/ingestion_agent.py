"""Ingestion orchestration: dedup, the source row, chunks, then the side steps.

Each model call lives in its own agent: tags (tagging_agent), memory_context
(memory_context_agent), entities (entity_agent), source summary (summary_agent).
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone

from agents.entity_agent import store_entities_for_chunks
from agents.memory_context_agent import (
    VALID_MEMORY_CONTEXTS,
    classify_memory_context,
    crossref_experience_context,
)
from agents.summary_agent import generate_source_summary
from agents.tagging_agent import extract_tags
from memory import source_store
from memory.source_store import SourceOriginal
from memory.vector_store import invalidate_bm25_cache, query_by_hash, upsert_chunks
from memory.hierarchy_store import assign_source_to_topic, source_node_exists, upsert_source_node
from utils import language
from utils.chunker import chunk_text

logger = logging.getLogger(__name__)


class ReplaceMismatch(ValueError):
    """A replace whose new text isn't the target source's text, when that is
    what made it replaceable (an exact-text match)."""


def compute_content_hash(content: str) -> str:
    normalised = content.strip().lower()
    return hashlib.sha256(normalised.encode()).hexdigest()


def ingest_content(
    content: str,
    source_type: str,
    source_title: str | None = None,
    *,
    user_id: str,
    original: SourceOriginal,
    memory_context: str | None = None,
    replace_source_id: str | None = None,
    reported_lang: str | None = None,
    refresh_unchanged: bool = False,
    replace_requires_same_text: bool = False,
) -> dict:
    """Ingest content into the knowledge base.

    content is the extracted text; original is what the user gave us and how it
    was extracted (stored in `sources`, see memory/source_store.py).

    memory_context: "work" | "personal_project" | "learning" | "observation" | None
        When None, the Haiku language pattern classifier is run to infer context
        automatically. Explicitly provided values are always used as-is.

    replace_source_id: an existing source this content replaces in place (same
        source_id; the new chunks are written first, then the row switches to them
        and the old chunks are deleted, see source_store.begin_replace). Used for
        the business profile note.

    reported_lang: the language a provider reported for this text (Supadata's
        `lang`), used only when the text is too short to identify.

    refresh_unchanged: the user chose Replace, so replace_source_id is replaced
        even when its text is unchanged (new title, URL, author, extractor).
        Without it an unchanged text is a duplicate and nothing is paid for (the
        business profile note saved with the same answers).

    replace_requires_same_text: replace_source_id was offered because its text
        matched (no file or URL to compare), so the new text must still be that
        source's text; otherwise ReplaceMismatch, before any model call or write.

    Raises utils.language.UnsupportedLanguage, before any model call or write,
    when the text is in a language the embedder can't search.

    Returns dict with keys: chunks_stored, tags, suggested_context (when inferred).
    """
    chunks = chunk_text(content)
    if not chunks:
        return {"chunks_stored": 0, "tags": []}
    lang = language.require_supported(content, reported_lang)

    # Deduplication check — skip Claude call entirely if content already exists
    content_hash = compute_content_hash(content)
    existing = query_by_hash(content_hash, user_id=user_id)
    is_target = bool(existing and replace_source_id and existing["source_id"] == replace_source_id)
    if replace_requires_same_text and not is_target:
        raise ReplaceMismatch("This source can't be replaced with different content.")
    if existing and not (is_target and refresh_unchanged):
        return {
            "chunks_stored": existing["chunk_count"],
            "tags": existing["tags"],
            "duplicate": True,
            "duplicate_source_id": existing["source_id"],
        }

    tags = extract_tags(content, user_id=user_id)

    # Infer memory_context when not explicitly provided.
    # Priority: experience cross-reference (deterministic) → Haiku classifier (LLM).
    # Store the suggestion so the caller can surface it in the response.
    context_was_inferred = False
    if memory_context is None:
        crossref = crossref_experience_context(content, user_id)
        if crossref:
            memory_context = crossref
            logger.info("memory_context inferred via experience cross-ref: %s", memory_context)
        else:
            memory_context = classify_memory_context(content, user_id=user_id)
        context_was_inferred = True
    elif memory_context not in VALID_MEMORY_CONTEXTS:
        logger.warning("invalid memory_context %r — falling back to classifier", memory_context)
        crossref = crossref_experience_context(content, user_id)
        memory_context = crossref or classify_memory_context(content, user_id=user_id)
        context_was_inferred = True

    if source_title is None:
        # Derive a human-readable title from the first 80 chars of content
        first_line = content.strip().splitlines()[0].strip()
        source_title = (first_line[:80] + "…") if len(first_line) > 80 else first_line

    ingested_at = datetime.now(timezone.utc).isoformat()

    # Generate source_id here so it's accessible for hierarchy persistence
    source_id = replace_source_id or str(uuid.uuid4())
    begin = source_store.begin_replace if replace_source_id else source_store.begin_source
    write = begin(user_id, source_id, original, title=source_title,
                  extracted_text=content, content_hash=content_hash, lang=lang)
    try:
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
            ingest_id=write.ingest_id,
        )
    except Exception:
        write.abort()
        raise
    write.commit()

    # Invalidate BM25 cache so the next generation request picks up the new
    # corpus. Safe to call even if no cache entry exists yet.
    invalidate_bm25_cache(user_id)

    # Entity extraction — runs per chunk after successful storage.
    # Wrapped in try/except: a failure here must NEVER fail ingestion.
    extracted_entity_names: list[str] = []
    try:
        extracted_entity_names = store_entities_for_chunks(
            chunks, source_id=source_id, ingest_id=write.ingest_id, user_id=user_id
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
        if replace_source_id or not source_node_exists(source_id, user_id=user_id):
            source_summary = generate_source_summary(content, user_id=user_id)
            topic_id = assign_source_to_topic(source_id, tags, user_id=user_id)
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
