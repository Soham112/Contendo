"""Approval of the final text, with explicit resolution of each claim flag."""
import logging

import anthropic

from agents.grounding_agent import check_grounding
from llm.client import StructuredOutputError
from memory import approval_store
from memory.trace_store import get_trace_sources

logger = logging.getLogger(__name__)


def verification_flag() -> dict:
    """The flag for text that could not be checked against its sources."""
    return {"id": "verification_unavailable", "sentence": "", "text": "",
            "reason": "We couldn't verify this text against its sources. Review its facts before approving."}


def review_text(user_id: str, content: str, media: list, post_id: int | None, trace_id: str | None) -> dict:
    trace = get_trace_sources(user_id, trace_id=trace_id, post_id=post_id)
    if trace is None:
        flags = [verification_flag()]
    else:
        outputs = trace.get("node_outputs") or {}
        grounding = outputs.get("grounding")
        if grounding and outputs.get("final_post") == content:
            flags = grounding["flags"]
        else:
            state = {"user_id": user_id, "profile": trace.get("profile_snapshot") or {},
                     "topic": trace.get("topic", ""), "context": trace.get("context", ""),
                     "retrieval_bundle": {"chunks": trace.get("retrieved") or []},
                     "models": outputs.get("models")}
            try:
                flags = check_grounding(state, content)
            except (anthropic.APIError, StructuredOutputError) as exc:
                logger.warning("approval grounding incomplete category=%s", type(exc).__name__)
                flags = [verification_flag()]
    return approval_store.create_review(user_id, content=content, media=media, post_id=post_id, flags=flags)


def approve_text(user_id: str, review_id: str, content: str, accepted: list[str]) -> dict:
    row = approval_store.get_review(user_id, review_id)
    if row is None:
        raise ValueError("Review not found. Check the final text again.")
    if row["content"] != content:
        raise ValueError("The text changed. Check and approve the final text again.")
    required = {flag["id"] for flag in row["flags"]}
    if set(accepted) != required:
        raise ValueError("Edit the text or explicitly accept each flagged claim before approval.")
    if row.get("approved_at"):
        return row
    approved = approval_store.approve(user_id, review_id, content, sorted(required))
    if approved is None:
        raise ValueError("The review changed. Check the final text again.")
    return approved


def matches_approval(user_id: str, approval_id: str | None, content: str, media: list, post_id: int | None) -> bool:
    row = approval_store.get_review(user_id, approval_id)
    return bool(row and row.get("approved_at") and row["content"] == content
                and row.get("media", []) == media and row.get("post_id") == post_id
                and set(row.get("accepted_flag_ids") or []) == {flag["id"] for flag in row["flags"]})
