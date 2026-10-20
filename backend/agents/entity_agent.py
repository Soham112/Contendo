"""Named entities per chunk of an ingested source: one Haiku call per chunk,
run in parallel, stored in the entity tables."""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from llm.client import HAIKU, complete
from memory.entity_store import upsert_chunk_entities, upsert_entity
from memory.vector_store import chunk_row_id

logger = logging.getLogger(__name__)

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


def extract_entities_for_chunk(chunk_text: str, *, user_id: str) -> list[dict]:
    """Extract named entities from a single chunk via Claude Haiku.

    Returns list of dicts: [{entity_name, entity_type, relationship_type}].
    Returns [] on any failure — never blocks ingestion.
    """
    try:
        message = complete(
            model=HAIKU,
            max_tokens=300,
            system=ENTITY_EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Extract entities from:\n\n{chunk_text}"}],
            user_id=user_id,
            event_type="ingest_entities",
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


def store_entities_for_chunks(
    chunks: list[str],
    source_id: str,
    ingest_id: str,
    user_id: str,
) -> list[str]:
    """Extract entities for all chunks in parallel and persist to entity tables.

    Runs Haiku calls concurrently (one per chunk) via ThreadPoolExecutor.
    All failures are caught and logged — never blocks ingestion.
    Chunk ids are those upsert_chunks wrote (vector_store.chunk_row_id).

    Returns the deduplicated list of entity names that were successfully stored.
    Used by the consolidation trigger to check which entities crossed the threshold.
    """
    stored_entity_names: list[str] = []
    names_lock = threading.Lock()

    def process_chunk(index: int, text: str) -> None:
        chunk_id = chunk_row_id(source_id, ingest_id, index)
        raw_entities = extract_entities_for_chunk(text, user_id=user_id)
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
