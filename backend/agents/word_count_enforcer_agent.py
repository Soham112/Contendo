import asyncio
import logging
import os

import anthropic
from dotenv import load_dotenv

from pipeline.state import PipelineState
from memory.usage_store import log_usage_event

load_dotenv()

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

_HAIKU = "claude-haiku-4-5-20251001"

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
- Output only the trimmed post — no commentary, no preamble

Current word count: {current_count}
Target: {min_words}–{max_words} words

Post:
{post}"""

_EXPAND_PROMPT = """You are a precise editor. Expand this post slightly to reach at least {min_words} words.

Rules:
- Add one specific detail, concrete example, or clarifying sentence — not filler
- Preserve the voice and meaning exactly
- Stay under {max_words} words
- Output only the expanded post — no commentary, no preamble

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
    If under: asks Haiku to expand with one specific detail, not filler.

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
            prompt_text = _TRIM_PROMPT.format(
                min_words=min_words,
                max_words=max_words,
                current_count=word_count,
                post=post,
            )
            action = "trim"
        else:
            prompt_text = _EXPAND_PROMPT.format(
                min_words=min_words,
                max_words=max_words,
                current_count=word_count,
                post=post,
            )
            action = "expand"

        msg = client.messages.create(
            model=_HAIKU,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt_text}],
        )

        adjusted = msg.content[0].text.strip()
        new_count = _count_words(adjusted)
        logger.info(
            "word_count_enforcer: action=%s, after=%d words (was %d)",
            action, new_count, word_count,
        )
        state["current_draft"] = adjusted

        try:
            asyncio.get_running_loop().create_task(log_usage_event(
                user_id=user_id,
                event_type="word_count_enforcer",
                input_tokens=msg.usage.input_tokens,
                output_tokens=msg.usage.output_tokens,
                model="haiku",
            ))
        except RuntimeError:
            pass

    except Exception as exc:
        logger.warning(
            "word_count_enforcer: unhandled error — returning post unchanged. error=%s", exc
        )

    return state
