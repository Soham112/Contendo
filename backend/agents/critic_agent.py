import json
import logging
import re

from llm.client import HAIKU, complete
from pipeline.state import PipelineState
from memory.profile_store import profile_to_context_string
from utils.frames import authorship, chunk_field, chunk_frame

logger = logging.getLogger(__name__)

_ARCHETYPE_NAMES: dict[str, str] = {
    "incident_report": "Incident Report / Retrospective",
    "contrarian_take": "Contrarian Take",
    "personal_story": "Personal Story",
    "teach_me_something": "Teach Me Something",
    "list_that_isnt": "List That Isn't",
    "prediction_bet": "Prediction / Bet",
    "before_after": "Before & After",
}

CRITIC_PROMPT = """You are a content critic. Your job is to diagnose weaknesses in a LinkedIn post draft before it is humanized. You diagnose only: you never write any part of the post.

Topic as given: {topic}
Additional context: {context}

Examine the draft across five dimensions, in this order:

1. TOPIC — Does the post stay on the topic as given (and the additional context, if any)? Flag any drift away from it, including turns toward the author's opinions, expertise or work that the topic does not ask for.
2. HOOK — Does the opening sentence stop a scroller immediately? Is it specific and surprising, or generic and forgettable?
3. SUBSTANCE — Does the draft use the ideas in the knowledge base chunks, or make vague claims any post could make? Judge substance only against what the chunks, the topic and the context actually contain.
4. STRUCTURE — Does the draft follow the expected pattern for a {archetype_name} post? Is the order of sections correct?
5. VOICE — Does this sound like the specific person in the profile, or like generic LinkedIn content?

Profile summary (voice reference only):
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
{experience_rule}

For each dimension, return a verdict ("strong" or "needs_work") and — if "needs_work" — one fix that follows the rules above. If "strong", set fix to null.

Return ONLY valid JSON with this exact structure — no preamble, no explanation, no markdown fences:
{{"topic": {{"verdict": "strong", "fix": null}}, "hook": {{"verdict": "strong", "fix": null}}, "substance": {{"verdict": "strong", "fix": null}}, "structure": {{"verdict": "strong", "fix": null}}, "voice": {{"verdict": "strong", "fix": null}}, "overall": "postable"}}

Use this exact shape — replace values with your actual verdicts and fix instructions."""

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


_NEUTRAL_BRIEF: dict = {
    "topic": {"verdict": "strong", "fix": None},
    "hook": {"verdict": "strong", "fix": None},
    "substance": {"verdict": "strong", "fix": None},
    "structure": {"verdict": "strong", "fix": None},
    "voice": {"verdict": "strong", "fix": None},
    "overall": "postable",
}


def _parse_critic_response(raw: str) -> dict:
    """Three-attempt JSON parse with neutral fallback."""
    attempts = [
        lambda r: json.loads(r),
        lambda r: json.loads(
            r.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        ),
        lambda r: json.loads(re.search(r"\{.*\}", r, re.DOTALL).group()),
    ]
    for attempt in attempts:
        try:
            return attempt(raw)
        except Exception:
            continue
    logger.warning("Critic agent: JSON parse failed, using neutral brief. Raw: %.200s", raw)
    return dict(_NEUTRAL_BRIEF)


def critic_node(state: PipelineState) -> PipelineState:
    """Diagnose the draft and write critic_brief to pipeline state.

    Skipped for draft quality mode (sets critic_brief={} immediately).
    All exceptions caught — sets critic_brief={} and continues so the
    pipeline never breaks.
    """
    if state.get("quality") == "draft":
        state["critic_brief"] = {}
        return state

    try:
        archetype_key = state.get("archetype") or "incident_report"
        archetype_name = _ARCHETYPE_NAMES.get(archetype_key, "Incident Report / Retrospective")

        profile = state.get("profile", {})
        profile_context = profile_to_context_string(profile) if profile else ""

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

        message = complete(
            model=HAIKU,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
            user_id=state["user_id"],
            event_type="critic",
        )

        raw = message.content[0].text.strip()
        state["critic_brief"] = _parse_critic_response(raw)

    except Exception as e:
        logger.warning("Critic agent failed: %s — setting critic_brief={}, pipeline continues", e)
        state["critic_brief"] = {}

    return state
