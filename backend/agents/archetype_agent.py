"""Chooses a post's archetype (its structure) from what the sources can support.

The material comes first: the code works out which archetypes are allowed from
the chunks' authorship, and the model picks only among those. A story-type
archetype (one that tells something that happened to the author) is kept only
when the model names the self-authored note that describes the event and quotes
a sentence from it, and the code finds that sentence in that note; otherwise
the post gets the neutral General Post. A failed call also gets General Post.
Every decision, including downgrades, is logged and stored in the trace.
"""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from llm.client import HAIKU, TruncatedStructuredOutputError, complete_structured
from pipeline.state import PipelineState
from utils.formatters import ARCHETYPES, GENERAL_ARCHETYPE, STORY_ARCHETYPES
from utils.frames import chunk_field, chunk_tags, is_self_authored

logger = logging.getLogger(__name__)

# With no notes to write from, only shapes that need no material are offered.
_OPINION_ARCHETYPES = ("contrarian_take", "teach_me_something", GENERAL_ARCHETYPE)

ARCHETYPE_PROMPT = """You are choosing the structure for a post. Choose by what the author has to write from, not by how the topic is phrased.

Topic: {topic}
Additional context: {context}
Format: {format}

What the author has to write from:
{material}

Post types you may choose from (choose one of these keys and nothing else):
{options}

Rules:
- Pick the type whose structure the material above can fill.
- Choose "general" when no other type clearly fits.{story_rule}"""

_STORY_RULE = """
- These types tell something that happened to the author: {story_keys}. Choose one only if one of the author's own notes above describes the event this post is about. Then give that note's number as event_note, and copy one sentence from that note, word for word, that describes the event as event_quote. If no own note describes the event, choose a different type."""


class ArchetypeChoice(BaseModel):
    archetype: str = Field(description="One of the offered post type keys.")
    event_note: int | None = Field(
        default=None,
        description="For a type that tells something that happened to the author: the number of "
                    "the author's own note that describes the event. Otherwise null.",
    )
    event_quote: str | None = Field(
        default=None,
        description="For those types: one sentence copied word for word from that note, describing "
                    "the event. Otherwise null.",
    )


# A quote has to be a sentence, not a word that would match anywhere.
_MIN_QUOTE_WORDS = 4


def _normalise(text: str) -> str:
    """Lower-case and collapse whitespace: the only differences a verbatim quote may have."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def quote_is_in_note(quote: str | None, note: dict) -> bool:
    """Whether quote appears word for word (whitespace and case aside) in the note's text.

    This proves the sentence is really in the note the model cited. Whether the
    sentence describes an event is the model's judgement; the code cannot check it.
    """
    wanted = _normalise(quote or "")
    if len(wanted.split()) < _MIN_QUOTE_WORDS:
        return False
    return wanted in _normalise(chunk_field(note, "text") or chunk_field(note, "content"))


def allowed_archetypes(perspective: str, self_authored_count: int) -> list[str]:
    """Archetype keys the sources allow, in registry order.

    opinion perspective (nothing to write from): opinion, explainer and general only.
    Otherwise every non-story type, plus the story types when at least one chunk
    is self-authored (the model must still name the note that describes the event).
    """
    if perspective == "opinion":
        return [key for key in ARCHETYPES if key in _OPINION_ARCHETYPES]
    return [key for key in ARCHETYPES if key not in STORY_ARCHETYPES or self_authored_count > 0]


def _material(own: list[dict], external: list[dict]) -> str:
    """Own notes numbered and in full (the model has to judge whether one
    describes an event); external sources by type and tags only. No titles:
    see the stopgap note on utils.frames.format_chunks_by_frame."""
    lines: list[str] = []
    if own:
        lines.append("The author's own notes:")
        for i, chunk in enumerate(own, 1):
            lines.append(f"[{i}]\n{chunk_field(chunk, 'text') or chunk_field(chunk, 'content')}")
    if external:
        kinds = sorted({
            f"{chunk_field(c, 'source_type') or 'article'} on {', '.join(sorted(chunk_tags(c))) or 'this topic'}"
            for c in external
        })
        lines.append("Things the author read, watched or saved (not the author's own experience): "
                     + "; ".join(kinds))
    return "\n\n".join(lines) if lines else "No notes on this topic. Only the topic and context above."


def choose_archetype(state: PipelineState) -> dict[str, Any]:
    """Pick the archetype for this post.

    Returns {archetype, chosen, allowed, event_note, event_quote, downgraded_from, reason}:
    `archetype` is what the post will use; `chosen` is what the model answered
    (None when the call failed); `downgraded_from` and `reason` are set when
    the two differ.
    """
    profile = state.get("profile") or {}
    perspective = state.get("perspective") or "opinion"
    chunks = [] if perspective == "opinion" else (state.get("retrieval_bundle") or {}).get("chunks", [])
    own = [c for c in chunks if is_self_authored(c, profile)]
    external = [c for c in chunks if not is_self_authored(c, profile)]
    allowed = allowed_archetypes(perspective, len(own))
    story_keys = [key for key in allowed if key in STORY_ARCHETYPES]

    decision: dict[str, Any] = {
        "archetype": GENERAL_ARCHETYPE, "chosen": None, "allowed": allowed,
        "event_note": None, "event_quote": None, "downgraded_from": None, "reason": None,
    }

    def fall_back(reason: str, chosen: str | None) -> dict[str, Any]:
        logger.warning("archetype: %s (model chose %r); using %r", reason, chosen, GENERAL_ARCHETYPE)
        return {**decision, "chosen": chosen, "downgraded_from": chosen, "reason": reason}

    try:
        choice = complete_structured(
            schema=ArchetypeChoice,
            tool_name="choose_post_type",
            tool_description="Record the post type chosen for this post.",
            model=HAIKU,
            max_tokens=300,
            messages=[{"role": "user", "content": ARCHETYPE_PROMPT.format(
                topic=state.get("topic", ""),
                context=(state.get("context") or "").strip() or "none",
                format=state.get("format", ""),
                material=_material(own, external),
                options="\n".join(f"- {key}: {ARCHETYPES[key].fits}" for key in allowed),
                story_rule=_STORY_RULE.format(story_keys=", ".join(story_keys)) if story_keys else "",
            )}],
            user_id=state["user_id"],
            event_type="archetype",
        )
    except TruncatedStructuredOutputError:
        return fall_back("truncated", None)
    except Exception as exc:
        return fall_back(f"inference failed: {exc}", None)

    chosen = choice.archetype.lower().strip()
    if chosen not in allowed:
        return fall_back("not an allowed type for these sources", chosen)
    if chosen not in STORY_ARCHETYPES:
        return {**decision, "archetype": chosen, "chosen": chosen}

    # A story type: `own` holds only self-authored notes, so a number outside it
    # cites nothing the author wrote; and the quoted sentence must be in that note.
    cited = {"event_note": choice.event_note, "event_quote": choice.event_quote}
    if not (choice.event_note and 1 <= choice.event_note <= len(own)):
        return {**fall_back("story type without an own note that describes the event", chosen), **cited}
    if not quote_is_in_note(choice.event_quote, own[choice.event_note - 1]):
        return {**fall_back("story type whose event quote is not in the cited own note", chosen), **cited}
    return {**decision, "archetype": chosen, "chosen": chosen, **cited}
