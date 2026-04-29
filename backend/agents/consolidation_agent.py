"""Consolidation agent — Phase 5.

Synthesises a structured memory summary for a single entity by grouping all
chunks that mention it into four context buckets and asking Claude Haiku to
produce a concise, factual brief.

Output shape (stored as a consolidation chunk in the embeddings table):

    entity: "React"
      direct experience (work): "Used at Stripe in production. Hit re-render issues."
      direct experience (personal): "Building Contendo frontend with React 18."
      learned knowledge: "Performance: memo, useMemo, virtualization."
      gap: "Haven't used React Native in production."

Trigger: called from ingestion_agent after a newly ingested source pushes an
entity's distinct-source count to 3 or above.
"""

import logging
import os

import anthropic

from memory.entity_store import get_chunk_ids_for_entity, get_entities_with_source_count
from memory.vector_store import get_chunks_by_ids
from memory.consolidation_store import upsert_consolidation_chunk, get_consolidation_chunk

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=2)

CONSOLIDATION_MODEL = "claude-haiku-4-5-20251001"

CONSOLIDATION_SYSTEM_PROMPT = """You are a knowledge consolidation assistant. You receive everything a specific person knows about a topic, organised by context bucket. Your job is to write a concise, factual memory brief in the exact format below.

Rules:
- Write only what is supported by the provided chunks. Do not invent facts.
- Each bucket line must be a single sentence, max 20 words.
- If a bucket has no content, omit that line entirely.
- The "gap" line describes what is clearly absent or untested based on what IS present — infer carefully.
- Do not use bullet points, headers, or markdown. Plain text only.
- Return ONLY the formatted brief, nothing else.

Format:
entity: "{entity_name}"
  direct experience (work): "..."
  direct experience (personal): "..."
  learned knowledge: "..."
  gap: "..."
"""

# Max chunks per entity fed to Haiku — avoids token bloat on high-mention entities
MAX_CHUNKS_PER_ENTITY = 12
# Max words per chunk excerpt passed to Haiku
MAX_WORDS_PER_CHUNK = 80


def _build_consolidation_input(
    entity_name: str,
    chunks: list[dict],
) -> str:
    """Group chunks by memory_context bucket and format them for Haiku input."""
    buckets: dict[str, list[str]] = {
        "work": [],
        "personal_project": [],
        "learning": [],
        "observation": [],
        "legacy": [],
    }

    for chunk in chunks[:MAX_CHUNKS_PER_ENTITY]:
        ctx = chunk.get("memory_context") or "legacy"
        if ctx not in buckets:
            ctx = "legacy"
        excerpt = " ".join((chunk.get("text") or chunk.get("content", "")).split()[:MAX_WORDS_PER_CHUNK])
        if excerpt:
            buckets[ctx].append(excerpt)

    lines = [f'Everything this person knows about "{entity_name}":\n']

    if buckets["work"]:
        lines.append("WORK CONTEXT (professional experience):")
        for i, ex in enumerate(buckets["work"][:4], 1):
            lines.append(f"  {i}. {ex}")

    if buckets["personal_project"]:
        lines.append("PERSONAL PROJECT CONTEXT:")
        for i, ex in enumerate(buckets["personal_project"][:4], 1):
            lines.append(f"  {i}. {ex}")

    if buckets["learning"]:
        lines.append("LEARNED FROM EXTERNAL SOURCES (articles, videos):")
        for i, ex in enumerate(buckets["learning"][:4], 1):
            lines.append(f"  {i}. {ex}")

    if buckets["observation"]:
        lines.append("OBSERVATIONS (patterns noticed):")
        for i, ex in enumerate(buckets["observation"][:3], 1):
            lines.append(f"  {i}. {ex}")

    if buckets["legacy"]:
        lines.append("OTHER:")
        for i, ex in enumerate(buckets["legacy"][:3], 1):
            lines.append(f"  {i}. {ex}")

    return "\n".join(lines)


def consolidate_entity(entity_id: str, entity_name: str, user_id: str) -> bool:
    """Synthesise and store a consolidation chunk for a single entity.

    Returns True if consolidation ran successfully, False otherwise.
    Failures are logged but never raised — caller must never crash on this.
    """
    try:
        chunk_ids = get_chunk_ids_for_entity(entity_id, user_id)
        if not chunk_ids:
            logger.debug("consolidate_entity: no chunks for entity %r — skipping", entity_name)
            return False

        chunks = get_chunks_by_ids(chunk_ids, user_id)
        if not chunks:
            return False

        consolidation_input = _build_consolidation_input(entity_name, chunks)

        message = _client.messages.create(
            model=CONSOLIDATION_MODEL,
            max_tokens=300,
            system=CONSOLIDATION_SYSTEM_PROMPT.replace("{entity_name}", entity_name),
            messages=[{"role": "user", "content": consolidation_input}],
        )
        brief = message.content[0].text.strip()

        if not brief:
            logger.warning("consolidate_entity: empty brief for entity %r", entity_name)
            return False

        upsert_consolidation_chunk(
            user_id=user_id,
            entity_id=entity_id,
            entity_name=entity_name,
            content=brief,
        )
        logger.info("consolidate_entity: consolidated %r for user %s", entity_name, user_id)
        return True

    except Exception as e:
        logger.warning("consolidate_entity: failed for %r: %s", entity_name, e)
        return False


def maybe_consolidate_entities(
    entity_names: list[str],
    user_id: str,
    min_sources: int = 3,
) -> None:
    """Check if any of the given entities have hit the consolidation threshold.

    Called post-ingest with the list of entity names extracted from the new
    source. Only entities that just crossed min_sources get consolidated —
    avoids re-running consolidation on every ingest for every entity.

    Already-consolidated entities are re-run to keep the brief fresh when
    new sources are added.
    """
    if not entity_names:
        return

    try:
        qualifying = get_entities_with_source_count(user_id, min_sources=min_sources)
        # Build name → (entity_id, source_count) map for the qualifying entities
        qualifying_map = {
            row["entity_name"].lower(): row
            for row in qualifying
        }

        touched_lower = {n.lower() for n in entity_names}
        to_consolidate = [
            row for name, row in qualifying_map.items()
            if name in touched_lower
        ]

        if not to_consolidate:
            return

        logger.info(
            "maybe_consolidate_entities: %d entities to consolidate for user %s",
            len(to_consolidate), user_id,
        )
        for row in to_consolidate:
            consolidate_entity(
                entity_id=row["entity_id"],
                entity_name=row["entity_name"],
                user_id=user_id,
            )

    except Exception as e:
        logger.warning("maybe_consolidate_entities: failed for user %s: %s", user_id, e)
