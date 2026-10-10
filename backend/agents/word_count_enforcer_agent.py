"""Pipeline A's length gate: word_count_enforcer_node asks Haiku to rewrite the
post shorter or longer. The single-writer trim (variants B and C), which only
deletes sentences, is agents/trim_agent.py.
"""

import logging

from llm.client import HAIKU, complete
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from utils.formatters import count_words
from utils.specifics import find_violations, guard_entry, guard_sources, retry_note

logger = logging.getLogger(__name__)

_TRIM_PROMPT = """You are a precise editor. Trim this post to {target_text}.

Rules:
- Preserve the voice, meaning, and key ideas exactly
- Cut weaker sentences, redundant phrases, and padding first
- Do not add any new content
- Never use the em dash character (—) anywhere in the output. Use a period or a comma instead
- Output only the trimmed post — no commentary, no preamble{specifics_retry}

Current word count: {current_count}
Target: {target_text}

Post:
{post}"""

_EXPAND_PROMPT = """You are a precise editor. Expand this post slightly to reach at least {min_words} words.

Rules:
- Expand only with material already in the post: elaborate a point it already makes, add a transition, or spell out a consequence of something it already says — not filler
- Never add or change any number, percentage, money amount, date, month, day of the week, duration, count, name or quoted figure, and do not introduce new examples, incidents, people or results
- Preserve the voice and meaning exactly
- Stay under {max_words} words
- Never use the em dash character (—) anywhere in the output. Use a period or a comma instead
- Output only the expanded post — no commentary, no preamble{specifics_retry}

Current word count: {current_count}
Target: {target_text}

Post:
{post}"""


def _count_words(text: str) -> int:
    return count_words(text)


def word_count_enforcer_node(state: PipelineState) -> PipelineState:
    """Final word-count gate — runs once after all pipeline passes are complete.

    Works to state["length_target"], the one target computed for this post
    (utils.formatters.resolve_length_target). Counts words in code. Within the
    target: unchanged. Over the maximum: asks Haiku to trim. Under the minimum:
    asks Haiku to expand using only material already in the post, but only when
    the target allows it (may_expand). A first post, or a post written from thin
    sources, is never expanded: a short post stays short.

    The result may not add or change facts: every specific must already be in
    the input post, the retrieved chunks or the profile. If it does, the call is
    retried once with the violations listed; if the retry still adds facts, the
    input post is kept. Retries are logged in state["specifics_guard"].

    Skipped for draft quality mode.
    All exceptions are caught — the pipeline never breaks.
    """
    if state.get("quality") == "draft":
        return state

    post = state.get("current_draft", "")
    if not post.strip():
        return state

    target = state.get("length_target")
    if not target:
        logger.info("word_count_enforcer: no word target for format=%r — skipping", state.get("format"))
        return state

    min_words, max_words = target["min_words"], target["max_words"]
    target_text = f"{min_words}–{max_words} words" if min_words else f"at most {max_words} words"
    word_count = _count_words(post)
    logger.info("word_count_enforcer: before=%d words, target=%s (%s)", word_count, target_text, target["basis"])

    if min_words <= word_count <= max_words:
        logger.info("word_count_enforcer: %d words is within range — no adjustment needed", word_count)
        return state
    if word_count < min_words and not target["may_expand"]:
        logger.info("word_count_enforcer: %d words is under %d, but a %s post is never expanded",
                    word_count, min_words, target["basis"])
        return state

    user_id = state["user_id"]

    try:
        if word_count > max_words:
            template, action = _TRIM_PROMPT, "trim"
        else:
            template, action = _EXPAND_PROMPT, "expand"

        def adjust(violations, event_type: str) -> str:
            msg = complete(
                model=HAIKU,
                max_tokens=2000,
                messages=[{"role": "user", "content": template.format(
                    min_words=min_words,
                    max_words=max_words,
                    target_text=target_text,
                    current_count=word_count,
                    post=post,
                    specifics_retry=retry_note(violations, no_specifics=bool(state.get("no_specifics"))),
                )}],
                user_id=user_id,
                event_type=event_type,
            )
            return msg.content[0].text.strip()

        sources = guard_sources(state, post)
        adjusted = adjust([], "word_count_enforcer")
        first = find_violations(adjusted, sources)
        if first:
            adjusted = adjust(first, "word_count_enforcer_retry")
            second = find_violations(adjusted, sources)
            state["specifics_guard"] = [*state.get("specifics_guard", []),
                                        guard_entry("word_count_enforcer", state.get("iterations", 0), first, second)]
            if second:
                logger.warning("word_count_enforcer: retry still added %s; keeping the input post",
                               [v.text for v in second])
                return state

        new_count = _count_words(adjusted)
        logger.info(
            "word_count_enforcer: action=%s, after=%d words (was %d)",
            action, new_count, word_count,
        )
        state["current_draft"] = adjusted
        record_draft(state, "word_count_enforcer")

    except Exception as exc:
        logger.warning(
            "word_count_enforcer: unhandled error — returning post unchanged. error=%s", exc
        )

    return state
