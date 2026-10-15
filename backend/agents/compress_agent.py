"""Compress (every single-writer variant): bring an over-length post towards its
maximum by shortening sentences. No sentence is deleted and the post is never
written again.

Why not the other two ways (docs/plans/single-writer.md, decision of
2026-10-10): deleting ranked sentences reversed a post's meaning in production
(the sentences that framed an opposing argument were the cheapest to delete),
and a whole-post rewrite re-generates text nobody asked to change.

One call to the run's draft model, at the draft's effort and budget, returns
shorter replacements for the sentences it chooses. Code decides which may be
used and splices them (pipeline/compress.py). One logical compress call per post;
identical transport retries per the shared client policy are allowed; never a
second compression of the same post:
whatever happens is recorded in state["compress_result"] and the run goes on.
"""

import logging

import anthropic

from agents.compress_prompt import COMPRESS_PROMPT, build_compress_prompt
from agents.draft_agent import _draft_budget, _effort, _usage_metadata
from llm.client import REFUSAL, StructuredOutputError, complete, message_text
from llm.models import model_for
from pipeline.compress import apply_replacements
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from utils.citations import Span, prose_word_count
from utils.draft_output import parse_fixes
from utils.frames import build_sources_block
from utils.sentences import split_spans

logger = logging.getLogger(__name__)


def _read(message, result: dict) -> list | None:
    """The replacements in the reply, or None with result["reason"] set when
    the reply cannot be used at all."""
    answer = message_text(message).strip()
    result["answer"] = answer
    if message.stop_reason == REFUSAL:
        result["reason"] = "refused"
    elif message.stop_reason == "max_tokens":
        result["reason"] = "truncated"
    elif not answer:
        result["reason"] = "empty_output"
    else:
        fixes, failures = parse_fixes(answer)
        result["format_failures"] = failures
        if fixes:
            return fixes
        missing = any(failure["kind"] == "fixes_tag_missing" for failure in failures)
        result["reason"] = "malformed_output: fixes_tag_missing" if missing else "no_replacements"
    return None


def compress_node(state: PipelineState) -> PipelineState:
    """Shorten an over-length post, sentence by sentence.

    state["compress_result"]:
      outcome "compressed"       the post is now within its maximum
      outcome "still_over"       every usable replacement is in place and the
                                 post is still too long; the shorter post is kept
      outcome "compress_failed"  the reply could not be used and the post is
                                 exactly as it was; reason says why: "refused",
                                 "truncated", "empty_output",
                                 "malformed_output: ...", "no_replacements",
                                 "api_error: ...", "response_invalid"
      accepted   [{sentence, before, after, words_before, words_after}]
      rejected   [{sentence, reason, text}]   (reasons: pipeline/compress.py)
      words_before, words_after, max_words    prose words, as the length check counts
      model, stop_reason, input_tokens, output_tokens, answer, format_failures
    """
    post = state.get("current_draft", "")
    spans = [Span.from_dict(c) for c in state.get("citations") or []]
    max_words = state["length_target"]["max_words"]
    words_before = prose_word_count(post)
    model = model_for(state, "draft")
    result = {"outcome": "compress_failed", "reason": None, "model": model, "stop_reason": None,
              "max_words": max_words, "words_before": words_before, "words_after": words_before,
              "accepted": [], "rejected": [], "format_failures": []}
    state["compress_result"] = result

    sources = build_sources_block((state.get("retrieval_bundle") or {}).get("chunks", []), state["profile"])
    prompt = build_compress_prompt(sources.text, [sentence for _, sentence in split_spans(spans)],
                                   words_before, max_words)
    fixes = None
    try:
        message = complete(
            model=model,
            max_tokens=_draft_budget(state, model),
            system=COMPRESS_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            user_id=state["user_id"],
            event_type="compress",
            usage_metadata=_usage_metadata(state),
            **_effort(state, model),
        )
    except StructuredOutputError:
        result["reason"] = "response_invalid"
    except anthropic.APIError as exc:
        result["reason"] = f"api_error: {type(exc).__name__}"
    else:
        result.update(stop_reason=message.stop_reason, input_tokens=message.usage.input_tokens,
                      output_tokens=message.usage.output_tokens)
        fixes = _read(message, result)

    if fixes is None:
        logger.warning("compress: failed (%s); the post stays at %d words against a maximum of %d",
                       result["reason"], words_before, max_words)
        return state

    compressed = apply_replacements(post, spans, fixes)
    result["accepted"], result["rejected"] = list(compressed.accepted), list(compressed.rejected)
    if compressed.accepted:
        state["current_draft"] = compressed.text
        state["citations"] = [span.as_dict() for span in compressed.spans]
        record_draft(state, "compress")
    result["words_after"] = prose_word_count(state["current_draft"])
    result["outcome"] = "compressed" if result["words_after"] <= max_words else "still_over"
    if result["rejected"] or result["outcome"] == "still_over":
        logger.warning("compress: %s; %d accepted, %d rejected %s; %d words against a maximum of %d",
                       result["outcome"], len(result["accepted"]), len(result["rejected"]),
                       [entry["reason"] for entry in result["rejected"]], result["words_after"], max_words)
    return state
