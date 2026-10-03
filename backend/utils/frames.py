"""Attribution frames: how each retrieved chunk may be written about.

One function decides a chunk's frame, so the drafter's frame block, the critic,
the specifics guard and the generation trace all agree on which chunks are the
user's own experience (SELF_FRAMES) and which are external knowledge.
"""

from typing import Any

# Frames for content the user lived or built. Only these chunks can support a
# first-person incident ("I shipped...", "At Acme, we...").
SELF_FRAMES = frozenset({"PERSONAL_WORK", "PERSONAL_PROJECT", "PERSONAL"})

# Legacy chunks (memory_context NULL, ingested before it existed): source types
# the user writes themselves. "note" covers typed notes and Obsidian imports.
# Everything else stays external: article (URLs, scraped pages and file uploads,
# which ingest stores as "article"), youtube, image and saved_content.
SELF_SOURCE_TYPES = frozenset({"note", "personal_note"})


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


def chunk_field(chunk: dict, key: str) -> str:
    """A field from a flat chunk dict or its nested 'metadata' sub-dict, as a string."""
    val = chunk.get(key)
    if val is not None:
        return str(val)
    return str((chunk.get("metadata") or {}).get(key) or "")


def chunk_tags(chunk: dict) -> set[str]:
    raw = chunk_field(chunk, "tags")
    return {t.strip().lower() for t in raw.split(",") if t.strip()} if raw else set()


def chunk_frame(chunk: dict, profile: dict) -> str:
    """The frame for one chunk (strict priority).

    1. consolidation chunks          -> CONSOLIDATION
    2. memory_context (set at ingest): work -> PERSONAL_WORK,
       personal_project -> PERSONAL_PROJECT, observation -> OBSERVATION,
       learning -> EXPERT_OUTSIDER or LEARNING (never PERSONAL)
    3. legacy chunks without memory_context: source_type in SELF_SOURCE_TYPES -> PERSONAL
    4. otherwise EXPERT_OUTSIDER when a tag overlaps the profile's
       topics_of_expertise, else LEARNING_<SENIORITY>
    """
    node_type = chunk_field(chunk, "node_type") or (chunk.get("metadata") or {}).get("node_id", "")
    if node_type == "consolidation" or chunk_field(chunk, "source_type") == "consolidation":
        return "CONSOLIDATION"

    memory_context = chunk.get("memory_context") or (chunk.get("metadata") or {}).get("memory_context")
    if memory_context == "work":
        return "PERSONAL_WORK"
    if memory_context == "personal_project":
        return "PERSONAL_PROJECT"
    if memory_context == "observation":
        return "OBSERVATION"
    if memory_context != "learning" and chunk_field(chunk, "source_type") in SELF_SOURCE_TYPES:
        return "PERSONAL"

    topics_of_expertise = [t.lower().strip() for t in profile.get("topics_of_expertise", []) or []]
    tags = chunk_tags(chunk)
    in_expertise = any(
        any(exp in tag or tag in exp for exp in topics_of_expertise) for tag in tags
    ) if topics_of_expertise and tags else False
    return "EXPERT_OUTSIDER" if in_expertise else f"LEARNING_{infer_seniority_level(profile).upper()}"


def is_self_authored(chunk: dict, profile: dict) -> bool:
    return chunk_frame(chunk, profile) in SELF_FRAMES


def authorship(frame: str) -> str:
    """'self' for the user's own experience, 'external' for everything else."""
    return "self" if frame in SELF_FRAMES else "external"


def self_authored_texts(chunks: list[dict[str, Any]], profile: dict) -> list[str]:
    return [
        chunk_field(c, "text") or chunk_field(c, "content")
        for c in chunks
        if is_self_authored(c, profile)
    ]
