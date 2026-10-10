import logging
import re

from llm.client import SONNET, complete
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from memory.profile_store import profile_voice_context
from utils.formatters import STYLE_RULES, word_count_rule
from utils.specifics import find_violations, guard_entry, guard_sources, retry_note

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a humanizing editor. You take drafts that may still have AI-writing fingerprints and rewrite them to sound like a real human wrote them, specifically like the person described in the profile below.

Author voice (voice and style only; never a source of content, stories or facts):
{profile_context}

Facts are fixed. You may change only wording, rhythm and structure.
- Never add or change any number, percentage, money amount, date, month, day of the week, duration, count, name or quoted figure. You may drop a detail if you need to cut for length, but prefer cutting words over cutting facts.
- Every factual detail in your output must already be in the current draft. If a sentence feels vague, sharpen the wording, not the facts.
- Do not invent incidents, timelines, customers, people or results.
- Keep the draft's perspective. Never turn something the draft presents as read, watched or observed into something the author did, and never add a personal reaction, memory or connection to the author's own work that the draft does not state.
- Don't attribute feelings, reactions or habits to the author about a source (e.g. "I haven't been able to put down", "I kept seeing... until I came across") unless the draft states them. Present the source's idea and the author's view of it plainly.
- Never link facts as cause and effect, sequence or result unless the draft already states that link. Facts the draft keeps separate stay separate.
- The critic brief below describes problems, not content. It never permits a new fact, story, experience, name or number. If a fix can't be made without new facts, skip it.

{critic_section}{style_rules}

{word_count_rule}Current draft:
{current_draft}

{rewrite_instruction}{specifics_retry}"""


_QUOTED_RE = re.compile(
    r'"[^"\n]*"'            # "double quotes"
    r"|“[^”\n]*”"           # “curly double quotes”
    r"|‘[^’\n]*’"           # ‘curly single quotes’
    r"|(?<![\w])'(?:[^'\n]|(?<=\w)'(?=\w))+'(?![\w])"  # 'single quotes', apostrophes inside allowed
)
_EXAMPLE_RE = re.compile(
    r"\(\s*(?:e\.g\.|eg\.|i\.e\.|(?:for example|for instance|such as|like)\b)[^)]*\)"
    r"|[,;:]?\s*(?:\be\.g\.|\bfor example\b|\bfor instance\b)[^.;]*"
    r"|\b(?:replace (?:it |this )?with )?something like\b",
    re.I,
)


def strip_quoted(fix: str) -> str:
    """A critic fix without quoted text or worked examples: the problem and the
    direction only, never wording the humanizer could paste in as fact."""
    text = _QUOTED_RE.sub("", fix)
    text = _EXAMPLE_RE.sub("", text)
    text = re.sub(r"\(\s*[,;:]?\s*\)", "", text)        # empty parentheses left behind
    text = re.sub(r"([,;:])\s+(or|and)\b", r" \2", text)       # "Ground it: or connect" -> "Ground it or connect"
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"([,;:])\s*([.;])", r"\2", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _format_critic_brief(critic_brief: dict) -> tuple[str, str]:
    """Format critic_brief dict into (critic_section, rewrite_instruction) for SYSTEM_PROMPT.

    Returns empty critic_section and a preserve-structure instruction when the brief
    is empty (draft mode / error) or all areas are "strong".
    Returns a populated critic_section and a fix-first instruction when any area
    has verdict "needs_work".
    """
    _preserve = (
        "Rewrite the draft now. Preserve the structure and all factual content — "
        "only change the language and sentence patterns. Output only the rewritten post, no commentary."
    )
    _fix_first = (
        "Rewrite the draft now. Fix the flagged issues above first — in this order: "
        "topic, hook, substance, structure, voice. You may rewrite the hook entirely and restructure sections, "
        "using only facts already in the draft. Then do a full language humanization pass. "
        "Output only the rewritten post, no commentary."
    )

    # {} (draft mode) or an error marker (the critic failed): no critic-driven changes.
    if not critic_brief or critic_brief.get("error"):
        return "", _preserve

    _areas = ["topic", "hook", "substance", "structure", "voice"]
    flagged = []
    for area in _areas:
        entry = critic_brief.get(area, {})
        if isinstance(entry, dict) and entry.get("verdict") == "needs_work" and entry.get("fix"):
            fix = strip_quoted(str(entry["fix"]))
            if fix:
                flagged.append(f"- {area.upper()}: {fix}")

    if not flagged:
        return "", _preserve

    critic_section = (
        "CRITIC BRIEF — fix these issues before humanizing, in this order:\n"
        + "\n".join(flagged)
        + "\n\n"
    )
    return critic_section, _fix_first


def humanizer_node(state: PipelineState) -> PipelineState:
    """Rewrite the draft in the user's voice without adding or changing facts.

    Every specific in the rewrite (numbers, dates, durations, ...) must already be
    in the input draft, the retrieved chunks or the profile. If not, retry once
    with the violations listed; if the retry still adds facts, keep the input
    draft. Retries are logged in state["specifics_guard"].
    """
    if state.get("quality") == "draft":
        return state  # pass raw draft through unchanged

    profile = state["profile"]
    profile_context = profile_voice_context(profile)
    words_to_avoid = ", ".join(profile.get("words_to_avoid", []))
    current_draft = state["current_draft"]
    user_id = state["user_id"]
    iteration = state.get("iterations", 0) + 1
    state["iterations"] = iteration

    critic_section, rewrite_instruction = _format_critic_brief(state.get("critic_brief", {}))
    length_rule = word_count_rule(state.get("length_target"))

    def rewrite(violations, event_type: str) -> str:
        prompt = SYSTEM_PROMPT.format(
            profile_context=profile_context,
            style_rules=STYLE_RULES.format(words_to_avoid=words_to_avoid),
            current_draft=current_draft,
            critic_section=critic_section,
            rewrite_instruction=rewrite_instruction,
            word_count_rule=f"{length_rule}\n\n" if length_rule else "",
            specifics_retry=retry_note(violations, no_specifics=bool(state.get("no_specifics"))),
        )
        message = complete(
            model=SONNET,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            event_type=event_type,
        )
        return message.content[0].text.strip()

    sources = guard_sources(state, current_draft)
    rewritten = rewrite([], "humanize")
    first = find_violations(rewritten, sources)
    if first:
        rewritten = rewrite(first, "humanize_retry")
        second = find_violations(rewritten, sources)
        state["specifics_guard"] = [*state.get("specifics_guard", []),
                                    guard_entry("humanizer", iteration, first, second)]
        if second:
            logger.warning("humanizer: retry still added %s; keeping the input draft",
                           [v.text for v in second])
            return state

    state["current_draft"] = rewritten
    record_draft(state, "humanizer")
    return state
