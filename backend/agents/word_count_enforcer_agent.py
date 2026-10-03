import logging

from llm.client import HAIKU, complete
from pipeline.state import PipelineState
from pipeline.trace import record_draft
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

_TRIM_PROMPT = """You are a precise editor. Trim this post to fit within {min_words}–{max_words} words.

Rules:
- Preserve the voice, meaning, and key ideas exactly
- Cut weaker sentences, redundant phrases, and padding first
- Do not add any new content
- Output only the trimmed post — no commentary, no preamble{specifics_retry}

Current word count: {current_count}
Target: {min_words}–{max_words} words

Post:
{post}"""

_EXPAND_PROMPT = """You are a precise editor. Expand this post slightly to reach at least {min_words} words.

Rules:
- Expand only with material already in the post: elaborate a point it already makes, add a transition, or spell out a consequence of something it already says — not filler
- Never add or change any number, percentage, money amount, date, month, day of the week, duration, count, name or quoted figure, and do not introduce new examples, incidents, people or results
- Preserve the voice and meaning exactly
- Stay under {max_words} words
- Output only the expanded post — no commentary, no preamble{specifics_retry}

Current word count: {current_count}
Target: {min_words}–{max_words} words

Post:
{post}"""


def _count_words(text: str) -> int:
    return len(text.split())


def _get_target_range(format_type: str, length: str) -> tuple[int, int] | None:
    """Return (min_words, max_words) for the given format/length, or None for tweet-based formats."""
    fmt = format_type.lower().strip()
    lng = length.lower().strip()
    format_lengths = _WORD_COUNT_MAP.get(fmt)
    if format_lengths is None:
        return None
    return format_lengths.get(lng, format_lengths["standard"])


def word_count_enforcer_node(state: PipelineState) -> PipelineState:
    """Final word-count gate — runs once after all pipeline passes are complete.

    Counts words in the post. If within target range: returns unchanged.
    If over: asks Haiku to trim while preserving voice and meaning.
    If under: asks Haiku to expand using only material already in the post.

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

    format_type = state.get("format", "linkedin post")
    length = state.get("length", "standard")
    target = _get_target_range(format_type, length)

    if target is None:
        logger.info(
            "word_count_enforcer: format=%r is tweet-based — skipping word count enforcement",
            format_type,
        )
        return state

    min_words, max_words = target
    word_count = _count_words(post)
    logger.info(
        "word_count_enforcer: before=%d words, target=%d–%d, format=%r, length=%r",
        word_count, min_words, max_words, format_type, length,
    )

    if min_words <= word_count <= max_words:
        logger.info("word_count_enforcer: %d words is within range — no adjustment needed", word_count)
        return state

    user_id = state.get("user_id", "default")

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
                    current_count=word_count,
                    post=post,
                    specifics_retry=retry_note(violations, no_specifics=bool(state.get("no_specifics"))),
                )}],
                user_id=user_id,
                event_type=event_type,
            )
            return strip_word_count_lines(msg.content[0].text.strip())

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
