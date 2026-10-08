import logging
import re

from llm.client import SONNET, complete
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from memory.profile_store import profile_to_context_string
from utils.post_cleanup import strip_word_count_lines
from utils.specifics import find_violations, guard_entry, guard_sources, retry_note

logger = logging.getLogger(__name__)

_WORD_COUNT_MAP = {
    "linkedin post": {
        "concise":   (100, 180),
        "standard":  (250, 350),
        "long-form": (450, 600),
    },
    "medium article": {
        "concise":   (350, 500),
        "standard":  (700, 900),
        "long-form": (1200, 1800),
    },
    # thread is tweet-count based, not word-count — no enforcement
}


def _get_word_count_rule(format_type: str, length: str) -> str:
    fmt = format_type.lower().strip()
    lng = length.lower().strip()
    format_lengths = _WORD_COUNT_MAP.get(fmt)
    if format_lengths is None:
        return ""
    min_w, max_w = format_lengths.get(lng, format_lengths["standard"])
    return (
        f"---\n"
        f"WORD COUNT RULE — this overrides everything else:\n"
        f"The final post must be {min_w}–{max_w} words.\n"
        f"Count before outputting. If over {max_w}, cut until you are within range.\n"
        f"Never exceed {max_w} words under any circumstance.\n"
        f"Do not print the word count.\n"
        f"---\n\n"
    )


SYSTEM_PROMPT = """You are a humanizing editor. You take drafts that may still have AI-writing fingerprints and rewrite them to sound like a real human wrote them, specifically like the person described in the profile below.

User profile:
{profile_context}

Facts are fixed. You may change only wording, rhythm and structure.
- Never add or change any number, percentage, money amount, date, month, day of the week, duration, count, name or quoted figure. You may drop a detail if you need to cut for length, but prefer cutting words over cutting facts.
- Every factual detail in your output must already be in the current draft. If a sentence feels vague, sharpen the wording, not the facts.
- Do not invent incidents, timelines, customers, people or results.
- The critic brief below describes problems, not content. It never permits a new fact, story, experience, name or number. If a fix can't be made without new facts, skip it.

{critic_section}AI writing patterns to eliminate:
- Sentences that start with "In today's..." or "It's important to note..."
- Overuse of transition words: "Furthermore", "Moreover", "Additionally", "In conclusion"
- Generic motivational framing: "unlock your potential", "game-changing", "transformative"
- Perfectly balanced sentence lengths; vary them aggressively
- Lists of three that feel formulaic (The three things are: A, B, and C)
- Passive voice where active would be stronger
- Em dashes used as clause connectors or parenthetical separators (e.g. 'the data was messy, noisy and sparse' or 'one feature, which had low fill rate, was dropped'). Replace with a period, a comma, or rewrite the sentence entirely. Em dashes are one of the strongest signals of AI-generated text and must never appear in the output.
- Hyphenated compound modifiers used decoratively (e.g. 'data-driven', 'production-ready', 'well-known', 'high-value' when plain language works just as well). Write 'drives decisions with data' not 'data-driven'. Only use hyphens when they are grammatically required and cannot be avoided.
- Words to avoid: {words_to_avoid}

Never use the em dash character (—) anywhere in the output. If you are about to write an em dash, stop and use a period or comma instead.

What to inject instead:
- Sentence variety: mix 4-word punches with longer, winding observations
- Incomplete thoughts that feel real: "Which, honestly, caught me off guard."
- Opinions stated with confidence, not hedged to death
- The writer's actual voice as described in the profile

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

    if not critic_brief:
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
    profile_context = profile_to_context_string(profile)
    words_to_avoid = ", ".join(profile.get("words_to_avoid", []))
    current_draft = state["current_draft"]
    user_id = state["user_id"]
    iteration = state.get("iterations", 0) + 1
    state["iterations"] = iteration

    critic_section, rewrite_instruction = _format_critic_brief(state.get("critic_brief", {}))
    word_count_rule = _get_word_count_rule(
        state.get("format", "linkedin post"),
        state.get("length", "standard"),
    )

    def rewrite(violations, event_type: str) -> str:
        prompt = SYSTEM_PROMPT.format(
            profile_context=profile_context,
            words_to_avoid=words_to_avoid,
            current_draft=current_draft,
            critic_section=critic_section,
            rewrite_instruction=rewrite_instruction,
            word_count_rule=word_count_rule,
            specifics_retry=retry_note(violations, no_specifics=bool(state.get("no_specifics"))),
        )
        message = complete(
            model=SONNET,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            event_type=event_type,
        )
        return strip_word_count_lines(message.content[0].text.strip())

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
