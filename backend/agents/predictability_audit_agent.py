import logging
import re

from llm.client import HAIKU, SONNET, complete
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from utils.specifics import find_violations, guard_entry, guard_sources, retry_note

logger = logging.getLogger(__name__)

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
- Make it unexpected: shorter, plainer, slightly imperfect, or unresolved
- Keep every number, percentage, money amount, date, day, duration, count, name and quoted figure exactly as in the sentence. Add none and remove none.
- Never use em dashes
- Output only the rewritten sentence — no explanation, no quotes, no preamble{specifics_retry}"""

_BURSTINESS_PROMPT = """Check this post for monotonous sentence rhythm.

If 3 or more consecutive sentences are within 4 words of each other in length, rewrite one of them to be either under 6 words or over 18 words to break the rhythm.

If the rhythm is already varied, return the post unchanged.

Change only sentence length and rhythm. Keep every number, percentage, money amount, date, month, day of the week, duration, count, name and quoted figure exactly as written. Add none and remove none.

Output only the full post — no explanation, no preamble.{specifics_retry}

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


# ── Node ──────────────────────────────────────────────────────────────────────

def _rewrite(post: str, flagged: str | None, violations, user_id: str, retry: bool,
             no_specifics: bool = False) -> str:
    """Steps 2 and 3 on post. Step 2 runs only when step 1 flagged a sentence."""
    suffix = "_retry" if retry else ""
    note = retry_note(violations, no_specifics=no_specifics)
    if flagged is not None:
        step2_msg = complete(
            model=SONNET,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": _REWRITE_SENTENCE_PROMPT.format(
                    post=post,
                    flagged_sentence=flagged,
                    specifics_retry=note,
                ),
            }],
            user_id=user_id,
            event_type=f"predictability_audit_step2{suffix}",
        )
        replacement = step2_msg.content[0].text.strip()
        logger.info("predictability_audit: replacement=%r", replacement[:120])
        post = _replace_sentence(post, flagged, replacement)

    step3_msg = complete(
        model=HAIKU,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": _BURSTINESS_PROMPT.format(post=post, specifics_retry=note),
        }],
        user_id=user_id,
        event_type=f"predictability_audit_step3{suffix}",
    )
    return step3_msg.content[0].text.strip()


def predictability_audit_node(state: PipelineState) -> PipelineState:
    """Three-step predictability audit that runs after humanizer_node.

    Step 1 (Haiku)  — find the single most AI-sounding sentence, or CLEAN.
    Step 2 (Sonnet) — rewrite only that sentence to be unexpected.
    Step 3 (Haiku)  — fix burstiness if 3+ consecutive sentences have similar length.

    The result may not add or change facts: every specific must already be in
    the node's input, the retrieved chunks or the profile. If it does, steps 2-3
    are retried once with the violations listed (reusing step 1's sentence); if
    the retry still adds facts, the input post is kept. Retries are logged in
    state["specifics_guard"].

    Skipped entirely for draft quality mode.
    All exceptions are caught — the pipeline never breaks.
    """
    if state.get("quality") == "draft":
        return state

    user_id = state["user_id"]
    post = state.get("current_draft", "")

    if not post.strip():
        return state

    try:
        # ── Step 1: Find the worst sentence ───────────────────────────────────
        step1_msg = complete(
            model=HAIKU,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": _FIND_WORST_PROMPT.format(post=post),
            }],
            user_id=user_id,
            event_type="predictability_audit_step1",
        )

        flagged: str | None = step1_msg.content[0].text.strip()

        if flagged.upper() == "CLEAN":
            logger.info("predictability_audit: step1=CLEAN, skipping step 2")
            flagged = None
        else:
            logger.info("predictability_audit: flagged=%r", flagged[:120])

        # ── Steps 2-3, checked for added facts ────────────────────────────────
        sources = guard_sources(state, post)
        audited = _rewrite(post, flagged, [], user_id, retry=False)
        first = find_violations(audited, sources)
        if first:
            audited = _rewrite(post, flagged, first, user_id, retry=True,
                               no_specifics=bool(state.get("no_specifics")))
            second = find_violations(audited, sources)
            state["specifics_guard"] = [*state.get("specifics_guard", []),
                                        guard_entry("predictability_audit", state.get("iterations", 0), first, second)]
            if second:
                logger.warning("predictability_audit: retry still added %s; keeping the input post",
                               [v.text for v in second])
                return state

        state["current_draft"] = audited
        record_draft(state, "predictability_audit")

    except Exception as exc:
        logger.warning(
            "predictability_audit: unhandled error — returning post unchanged. error=%s", exc
        )

    return state
