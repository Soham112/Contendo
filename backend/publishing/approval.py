"""Approval of the final text, with explicit resolution of each claim flag.

No model checks the text here (removed 2026-10-15, with the generation-time
grounding pass): approval locks the exact text, and the user reads and approves
it. The only flags are those a post generated before then stored with its
trace, shown while its text is unchanged."""
from memory import approval_store
from memory.trace_store import get_trace_sources


def review_text(user_id: str, content: str, media: list, post_id: int | None, trace_id: str | None) -> dict:
    trace = get_trace_sources(user_id, trace_id=trace_id, post_id=post_id)
    outputs = (trace or {}).get("node_outputs") or {}
    grounding = outputs.get("grounding")
    stored = bool(grounding) and outputs.get("final_post") == content
    flags = grounding["flags"] if stored else []
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
