"""Attribution frames and perspective: how retrieved material may be written about.

One function decides a chunk's frame, so the drafter's frame block, the critic,
the specifics guard and the generation trace all agree on which chunks are the
user's own experience (SELF_FRAMES) and which are external knowledge.

FRAMES is the single list of frames: the label each group of chunks gets in the
prompt and the rule for writing from it. The draft prompt's attribution rules
are generated from it, so the prompt cannot describe frames the code does not
produce. decide_perspective() turns the chunks' authorship into the post's
perspective (experience / learned / opinion / mixed).
"""

from dataclasses import dataclass
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


# ── The frame list ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Frame:
    label: str   # header over this frame's chunks in the knowledge base block
    rule: str    # how to write from chunks under that header


_OWN = ("First person. Tell only what the note describes: never add an incident, "
        "result, person, place or date to it.")
_EXTERNAL = ("Something the author read, watched or saved, not something the author did. "
             "Refer to it by what it is and what it covers (\"an article on...\", \"a talk on...\", "
             "\"a video about...\"); do not give it a title. Never present it as the author's own "
             "experience, and never connect it to the author's own work, background or life.")

# In prompt order. Every frame chunk_frame() can return is here, and nothing else.
FRAMES: dict[str, Frame] = {
    "CONSOLIDATION": Frame(
        "CONSOLIDATED SUMMARY",
        "A summary of what the author's notes say about this topic. Background only: absorb it, "
        "don't quote it. It cannot be the evidence for a first-person event.",
    ),
    "PERSONAL_WORK": Frame(
        "OWN EXPERIENCE: WORK",
        "Something the author did or built professionally. " + _OWN,
    ),
    "PERSONAL_PROJECT": Frame(
        "OWN EXPERIENCE: PERSONAL PROJECT",
        "The author's own side project or experiment. " + _OWN,
    ),
    "PERSONAL": Frame(
        "OWN EXPERIENCE: NOTES",
        "The author's own notes. " + _OWN,
    ),
    "OBSERVATION": Frame(
        "OBSERVATION",
        "A pattern the author has noticed. Write it as noticing (\"I keep seeing\", \"the pattern is\"), "
        "never as an event that happened to the author.",
    ),
    "EXPERT_OUTSIDER": Frame(
        "EXTERNAL SOURCE: IN THE AUTHOR'S FIELD",
        _EXTERNAL + " The author knows this field, so write about the idea with authority.",
    ),
    "LEARNING_SENIOR": Frame(
        "EXTERNAL SOURCE: LEARNING (senior voice)",
        _EXTERNAL + " Say what the source argues and give a firm judgement on it.",
    ),
    "LEARNING_MID": Frame(
        "EXTERNAL SOURCE: LEARNING (mid-career voice)",
        _EXTERNAL + " Say what the source argues and what you make of it, without hedging.",
    ),
    "LEARNING_JUNIOR": Frame(
        "EXTERNAL SOURCE: LEARNING (early-career voice)",
        _EXTERNAL + " Say plainly what the source argues and what stood out, without hedging.",
    ),
}

NO_CHUNKS_BLOCK = "(No notes relevant to this topic were found.)"


def format_chunks_by_frame(chunks: list[dict], profile: dict) -> str:
    """The knowledge base block for the drafter: chunks grouped under their
    frame's label, each with its source type and tags.

    STOPGAP: the source title is not shown, so sources are referred to by type
    and subject. Stored metadata doesn't record whether a title is real (a page,
    video or file name) or was derived from the content (a note's first 80
    characters), and a derived title must not be printed as a credit.
    Proper fix: record title_origin (provided | derived) at ingest, migrate and
    backfill existing rows, and credit by title only when provided. Planned for
    fix/ingest-attribution (see CODEBASE.md section 6). The title stays in the
    generation trace (retrieved[].source_title) for debugging.
    """
    if not chunks:
        return NO_CHUNKS_BLOCK
    by_frame: dict[str, list[dict]] = {}
    for chunk in chunks:
        by_frame.setdefault(chunk_frame(chunk, profile), []).append(chunk)

    lines: list[str] = []
    for key, frame in FRAMES.items():
        for i, chunk in enumerate(by_frame.get(key, [])):
            if i == 0:
                lines.append(f"{frame.label}:")
            source_type = chunk_field(chunk, "source_type") or "article"
            tags = ", ".join(sorted(chunk_tags(chunk))) or "none"
            lines.append(f"[source: {source_type} | tags: {tags}]")
            lines.append(chunk_field(chunk, "text") or chunk_field(chunk, "content"))
            lines.append("")
    return "\n".join(lines).strip()


def frame_rules(chunks: list[dict], profile: dict) -> str:
    """One writing rule per frame present in these chunks, keyed by the same
    label the knowledge base block uses. "" when there are no chunks."""
    present = {chunk_frame(chunk, profile) for chunk in chunks}
    return "\n\n".join(
        f"{frame.label}:\n{frame.rule}" for key, frame in FRAMES.items() if key in present
    )


# ── Perspective ───────────────────────────────────────────────────────────────

# Added to every perspective.
_NO_GENERALISING = (
    "\nDon't make claims about what most people, most founders or most teams do unless a source says so; "
    "state it as the author's view instead (\"I think many teams...\")."
)
# Added where the post draws on things the author read or watched.
_NO_INVENTED_REACTIONS = (
    "\nDon't attribute feelings, reactions or habits to the author about a source (e.g. \"I haven't been "
    "able to put down\", \"I kept seeing... until I came across\") unless a source or the request states them. "
    "Present the source's idea and the author's view of it plainly."
)

# What the post is written as, decided in code from the chunks' authorship.
PERSPECTIVES: dict[str, str] = {
    "experience": (
        "PERSPECTIVE: experience.\n"
        "The sources are the author's own notes. Write in first person, and only about what "
        "those notes describe."
        + _NO_GENERALISING
    ),
    "learned": (
        "PERSPECTIVE: learned.\n"
        "The sources are things the author read, watched or saved, not things the author did. "
        "Share what they say and what you make of it, and say where each idea came from by what the "
        "source is and what it covers (\"an article on...\", \"a talk on...\", \"a video about...\"), "
        "without giving it a title. "
        "Do not connect the material to the author's own work, career or life, and do not present "
        "any of it as something the author did, saw or went through."
        + _NO_INVENTED_REACTIONS + _NO_GENERALISING
    ),
    "opinion": (
        "PERSPECTIVE: opinion.\n"
        "The author's notes do not cover this topic. Write views and observations with their reasoning. "
        "Claim no event, result or experience, except one the author states in the topic or the "
        "additional context."
        + _NO_GENERALISING
    ),
    "mixed": (
        "PERSPECTIVE: mixed.\n"
        "Some sources are the author's own notes and some are things the author read or watched. "
        "Each point keeps its origin: first person only for what the author's own notes describe; "
        "everything else is attributed to where it came from, by what the source is and what it covers "
        "(\"an article on...\", \"a talk on...\"), without a title. Never merge the two in one sentence, and never "
        "stretch the author's experience to cover external material."
        + _NO_INVENTED_REACTIONS + _NO_GENERALISING
    ),
}


def decide_perspective(chunks: list[dict], profile: dict, *, opinion_only: bool = False) -> str:
    """experience (all chunks self-authored), learned (all external), mixed (both),
    or opinion (no chunks, or opinion_only: the post is written without its chunks)."""
    if opinion_only or not chunks:
        return "opinion"
    self_count = sum(is_self_authored(chunk, profile) for chunk in chunks)
    if self_count == len(chunks):
        return "experience"
    return "mixed" if self_count else "learned"
