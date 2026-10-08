import logging
from typing import Literal

from pydantic import BaseModel, Field

from llm.client import HAIKU, complete_structured
from pipeline.state import PipelineState
from memory.profile_store import profile_voice_context
from utils.formatters import get_archetype
from utils.frames import authorship, chunk_field, chunk_frame

logger = logging.getLogger(__name__)

class Verdict(BaseModel):
    verdict: Literal["strong", "needs_work"]
    fix: str | None = Field(default=None, description="One fix when the verdict is needs_work; null when strong.")


class CriticBrief(BaseModel):
    topic: Verdict
    hook: Verdict
    substance: Verdict
    structure: Verdict
    voice: Verdict
    overall: Literal["postable", "needs_work"]


CRITIC_PROMPT = """You are a content critic. Your job is to diagnose weaknesses in a LinkedIn post draft before it is humanized. You diagnose only: you never write any part of the post.

Topic as given: {topic}
Additional context: {context}

Examine the draft across five dimensions, in this order:

1. TOPIC — Does the post stay on the topic as given (and the additional context, if any)? Flag any drift away from it, including turns toward the author's opinions, expertise or work that the topic does not ask for.
2. HOOK — Does the opening sentence stop a scroller immediately? Is it specific and surprising, or generic and forgettable?
3. SUBSTANCE — Does the draft use the ideas in the knowledge base chunks, or make vague claims any post could make? Judge substance only against what the chunks, the topic and the context actually contain.
4. STRUCTURE — Does the draft follow the pattern of a {archetype_name} post, as far as the sources allow? Judge only the sections the chunks or the request have material for. A section the sources cannot fill is correctly left out: never count it as missing and never ask for it.
5. VOICE — Does this sound like the specific person in the profile, or like generic LinkedIn content?

Author voice (voice reference only; never a source of content or angles):
{profile_context}

Post archetype (structural reference): {archetype_name}
{mode_section}
Knowledge base chunks available, each labelled with its frame and authorship (self = the author's own experience; external = something the author read or watched). Check whether the draft uses them or ignores them:
{retrieved_chunks}

Draft to diagnose:
{current_draft}

Rules for every fix:
- Describe the problem and the direction to take, in your own words. The form to follow: the hook is generic; lead with the strongest point from the sources.
- Never write example sentences, replacement text, or anything in quotation marks. Never quote the draft or the chunks.
- Never suggest a name, number, date, time, place or event that is not already in the draft or the chunks.
- Never suggest connecting the post to the author's opinions, expertise, projects or work unless the topic or context asks for it. The profile is a voice reference, not a source of angles.
- Each chunk is a separate source. If the draft links facts from different chunks as cause and effect, sequence or result, and no single chunk states that link, mark SUBSTANCE "needs_work" and say which link to remove. Facts from separate notes stay separate.
{experience_rule}

For each dimension, give a verdict ("strong" or "needs_work") and — if "needs_work" — one fix that follows the rules above. If "strong", the fix is null. Set overall to "postable" only when every verdict is "strong"."""

_NO_SPECIFICS_MODE = """
MODE: opinion post without specifics. The author's notes don't cover this topic, and they asked for an opinion post anyway. The post must contain no numbers, dates, names, incidents, customers or results unless the topic or context gives them. Judge substance by the quality of the argument, never by whether it has specifics or stories.
"""

_NO_SELF_CHUNKS_RULE = (
    "- None of the chunks are self-authored. Never ask for personal experience, a story, an incident, "
    "a real example, or specific numbers or names: the author has given none for this topic. "
    "Ask instead for sharper reasoning, clearer structure, or better use of the chunks."
)
_SELF_CHUNKS_RULE = (
    "- Ask for first-person experience only where a self-authored chunk describes it, "
    "and say which chunk's point to use."
)


def _label_chunks(state: PipelineState) -> tuple[str, int]:
    """Chunks labelled with frame and authorship, and how many are self-authored."""
    profile = state.get("profile") or {}
    chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])
    if not chunks:
        flat = state.get("retrieved_chunks", [])
        return ("\n---\n".join(flat) if flat else "No knowledge base chunks available."), 0
    lines, self_count = [], 0
    for chunk in chunks:
        frame = chunk_frame(chunk, profile)
        who = authorship(frame)
        self_count += who == "self"
        source_type = chunk_field(chunk, "source_type") or "article"
        text = chunk_field(chunk, "text") or chunk_field(chunk, "content")
        lines.append(f"[frame: {frame} | authorship: {who} | source: {source_type}]\n{text}")
    return "\n---\n".join(lines), self_count


def critic_node(state: PipelineState) -> PipelineState:
    """Diagnose the draft and write critic_brief to pipeline state.

    Skipped for draft quality mode (sets critic_brief={} immediately).
    If the call or its structured answer fails, critic_brief is {"error": "..."}:
    an explicit marker, never a made-up "all strong" brief. The humanizer then
    makes no critic-driven changes, and the pipeline continues.
    """
    if state.get("quality") == "draft":
        state["critic_brief"] = {}
        return state

    try:
        archetype_name = get_archetype(state.get("archetype", "")).name

        profile = state.get("profile", {})
        profile_context = profile_voice_context(profile) if profile else ""

        chunks_text, self_count = _label_chunks(state)

        prompt = CRITIC_PROMPT.format(
            archetype_name=archetype_name,
            topic=state.get("topic", ""),
            context=(state.get("context") or "").strip() or "none",
            profile_context=profile_context,
            mode_section=_NO_SPECIFICS_MODE if state.get("no_specifics") else "",
            retrieved_chunks=chunks_text,
            current_draft=state.get("current_draft", ""),
            experience_rule=_SELF_CHUNKS_RULE if self_count else _NO_SELF_CHUNKS_RULE,
        )

        brief = complete_structured(
            schema=CriticBrief,
            tool_name="record_critique",
            tool_description="Record the diagnosis of the draft.",
            model=HAIKU,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
            user_id=state["user_id"],
            event_type="critic",
        )
        state["critic_brief"] = brief.model_dump()

    except Exception as e:
        logger.warning("critic: failed (%s); no critic-driven changes for this post", e)
        state["critic_brief"] = {"error": str(e)}

    return state
