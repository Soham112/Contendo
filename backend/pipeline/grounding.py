"""Bounded grounding at the generation boundary, after all text-changing steps."""
import logging

import anthropic

from agents.grounding_agent import check_grounding, repair_grounding
from llm.client import StructuredOutputError
from pipeline.checks import run_checks
from pipeline.finalise import finalise_marked
from pipeline.trace import record_draft
from utils.frames import build_sources_block

logger = logging.getLogger(__name__)
MAX_GROUNDING_REPAIRS = 2


def verification_flag() -> dict:
    return {"id": "verification_unavailable", "sentence": "", "text": "",
            "reason": "We couldn't verify this text against its sources. Review its facts before approving."}


def enforce_grounding(state: dict) -> dict:
    post = state.get("final_post", "")
    if not post.strip() or state.get("draft_truncated") or state.get("draft_refused") or state.get("draft_empty"):
        return state
    record = {"outcome": "needs_review", "flags": [], "attempts": [], "repairs": 0}
    state["grounding"] = record
    for attempt in range(MAX_GROUNDING_REPAIRS + 1):
        try:
            flags = check_grounding(state, post)
            record["flags"] = flags
            record["attempts"].append({"text": post, "flags": flags})
            if not flags:
                record["outcome"] = "verified"
                return state
            if attempt == MAX_GROUNDING_REPAIRS:
                return state
            marked = repair_grounding(state, post, flags)
            final, stripped = finalise_marked(marked, state.get("length_target"))
            index = build_sources_block((state.get("retrieval_bundle") or {}).get("chunks", []), state.get("profile") or {}).index
            if not stripped.spans or stripped.failures or any(
                span.basis == "uncited" or any(sid not in index for sid in span.sources) for span in stripped.spans
            ):
                raise StructuredOutputError("Grounding repair has missing or invalid citations")
            post = final.text
            state.update(current_draft=post, final_post=post, citations=[s.as_dict() for s in stripped.spans],
                         final_validation=final.record)
            state["source_index"] = index
            state["checks_final"] = run_checks(state, [])
            record["flags"] = []
            record["repairs"] += 1
            record_draft(state, "grounding_repair")
        except (anthropic.APIError, StructuredOutputError) as exc:
            record["error"] = type(exc).__name__
            record["flags"] = [*record["flags"], verification_flag()]
            logger.warning("grounding could not complete category=%s", type(exc).__name__)
            return state
    return state
