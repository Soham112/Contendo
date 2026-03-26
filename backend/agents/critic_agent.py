import anthropic
import json
import logging
import os
import re

from dotenv import load_dotenv

from pipeline.state import PipelineState
from memory.profile_store import profile_to_context_string

load_dotenv()

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

_ARCHETYPE_NAMES: dict[str, str] = {
    "incident_report": "Incident Report / Retrospective",
    "contrarian_take": "Contrarian Take",
    "personal_story": "Personal Story",
    "teach_me_something": "Teach Me Something",
    "list_that_isnt": "List That Isn't",
    "prediction_bet": "Prediction / Bet",
    "before_after": "Before & After",
}

CRITIC_PROMPT = """You are a content critic. Your job is to diagnose weaknesses in a LinkedIn post draft before it is humanized — not to write anything, just identify what needs fixing.

Examine the draft across four dimensions:

1. HOOK — Does the opening sentence stop a scroller immediately? Is it specific and surprising, or generic and forgettable?
2. SUBSTANCE — Are claims grounded in specific details, named examples, or real numbers from the knowledge base? Or vague generalities that any post could make?
3. STRUCTURE — Does the draft follow the expected pattern for a {archetype_name} post? Is the order of sections correct?
4. VOICE — Does this sound like the specific person in the profile, or like generic LinkedIn content?

Profile summary (voice reference):
{profile_context}

Post archetype (structural reference): {archetype_name}

Knowledge base chunks available (check whether the draft uses them or ignores them):
{retrieved_chunks}

Draft to diagnose:
{current_draft}

For each dimension, return a verdict ("strong" or "needs_work") and — if "needs_work" — one specific, actionable fix instruction. If "strong", set fix to null.

Return ONLY valid JSON with this exact structure — no preamble, no explanation, no markdown fences:
{{"hook": {{"verdict": "strong", "fix": null}}, "substance": {{"verdict": "strong", "fix": null}}, "structure": {{"verdict": "strong", "fix": null}}, "voice": {{"verdict": "strong", "fix": null}}, "overall": "postable"}}

Use this exact shape — replace values with your actual verdicts and fix instructions."""

_NEUTRAL_BRIEF: dict = {
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

        retrieved_chunks = state.get("retrieved_chunks", [])
        chunks_text = (
            "\n---\n".join(retrieved_chunks[:5])
            if retrieved_chunks
            else "No knowledge base chunks available."
        )

        prompt = CRITIC_PROMPT.format(
            archetype_name=archetype_name,
            profile_context=profile_context,
            retrieved_chunks=chunks_text,
            current_draft=state.get("current_draft", ""),
        )

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        state["critic_brief"] = _parse_critic_response(raw)

    except Exception as e:
        logger.warning("Critic agent failed: %s — setting critic_brief={}, pipeline continues", e)
        state["critic_brief"] = {}

    return state
