import asyncio
import logging
import os
import re

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
_SONNET = "claude-sonnet-4-6"

# ── Prompts ───────────────────────────────────────────────────────────────────

_FIND_WORST_PROMPT = """Read this post and return the single most AI-sounding sentence — the one that is too smooth, too resolved, or could have been written by any AI about this topic.

Rules:
- Return only the sentence, verbatim, with no explanation or punctuation outside the sentence itself
- If nothing sounds like AI, return only the word: CLEAN

Post:
{post}"""

_REWRITE_SENTENCE_PROMPT = """You are rewriting a single sentence in a social media post to sound more human and unexpected.

Full post (for voice context only — do not rewrite this):
{post}

Sentence to rewrite:
{flagged_sentence}

Rules:
- Rewrite only the sentence above
- Make it unexpected: shorter, more specific, slightly imperfect, or unresolved
- Never use em dashes
- Output only the rewritten sentence — no explanation, no quotes, no preamble"""

_BURSTINESS_PROMPT = """Check this post for monotonous sentence rhythm.

If 3 or more consecutive sentences are within 4 words of each other in length, rewrite one of them to be either under 6 words or over 18 words to break the rhythm.

If the rhythm is already varied, return the post unchanged.

Output only the full post — no explanation, no preamble.

Post:
{post}"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Split text into sentences by terminal punctuation."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if p.strip()]


def _replace_sentence(post: str, original: str, replacement: str) -> str:
    """Try exact string match first, then fuzzy word-overlap fallback."""
    # Exact match
    if original in post:
        return post.replace(original, replacement, 1)

    # Fuzzy: find best sentence by word overlap
    sentences = _split_sentences(post)
    orig_words = set(original.lower().split())
    best_idx = -1
    best_overlap = 0
    for i, s in enumerate(sentences):
        overlap = len(orig_words & set(s.lower().split()))
        if overlap > best_overlap:
            best_overlap = overlap
            best_idx = i

    threshold = max(1, len(orig_words) // 2)
    if best_idx >= 0 and best_overlap >= threshold:
        sentences[best_idx] = replacement
        return " ".join(sentences)

    logger.warning(
        "predictability_audit: could not match flagged sentence in post — "
        "returning post unchanged. flagged=%r",
        original[:80],
    )
    return post


def _log(user_id: str, event_type: str, msg: anthropic.types.Message, model: str) -> None:
    """Fire-and-forget usage log — same pattern as all other agents."""
    try:
        asyncio.get_running_loop().create_task(log_usage_event(
            user_id=user_id,
            event_type=event_type,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            model=model,
        ))
    except RuntimeError:
        pass  # No running event loop (e.g. in tests) — skip logging


# ── Node ──────────────────────────────────────────────────────────────────────

def predictability_audit_node(state: PipelineState) -> PipelineState:
    """Three-step predictability audit that runs after humanizer_node.

    Step 1 (Haiku)  — find the single most AI-sounding sentence, or CLEAN.
    Step 2 (Sonnet) — rewrite only that sentence to be unexpected.
    Step 3 (Haiku)  — fix burstiness if 3+ consecutive sentences have similar length.

    Skipped entirely for draft quality mode.
    All exceptions are caught — the pipeline never breaks.
    """
    if state.get("quality") == "draft":
        return state

    user_id = state.get("user_id", "default")
    post = state.get("current_draft", "")

    if not post.strip():
        return state

    try:
        # ── Step 1: Find the worst sentence ───────────────────────────────────
        step1_msg = client.messages.create(
            model=_HAIKU,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": _FIND_WORST_PROMPT.format(post=post),
            }],
        )
        _log(user_id, "predictability_audit_step1", step1_msg, "haiku")

        flagged = step1_msg.content[0].text.strip()

        if flagged.upper() == "CLEAN":
            logger.info("predictability_audit: step1=CLEAN, skipping step 2")
        else:
            logger.info("predictability_audit: flagged=%r", flagged[:120])

            # ── Step 2: Rewrite only that sentence ────────────────────────────
            step2_msg = client.messages.create(
                model=_SONNET,
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": _REWRITE_SENTENCE_PROMPT.format(
                        post=post,
                        flagged_sentence=flagged,
                    ),
                }],
            )
            _log(user_id, "predictability_audit_step2", step2_msg, "sonnet")

            replacement = step2_msg.content[0].text.strip()
            logger.info("predictability_audit: replacement=%r", replacement[:120])

            post = _replace_sentence(post, flagged, replacement)

        # ── Step 3: Burstiness fix ─────────────────────────────────────────────
        step3_msg = client.messages.create(
            model=_HAIKU,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": _BURSTINESS_PROMPT.format(post=post),
            }],
        )
        _log(user_id, "predictability_audit_step3", step3_msg, "haiku")

        post = step3_msg.content[0].text.strip()
        state["current_draft"] = post

    except Exception as exc:
        logger.warning(
            "predictability_audit: unhandled error — returning post unchanged. error=%s", exc
        )

    return state
