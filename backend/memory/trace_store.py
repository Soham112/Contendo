from typing import Any, Callable

from db.supabase_client import supabase


def save_generation_trace(row: dict[str, Any]) -> str:
    """Insert one generation_traces row (row must include user_id); return its id."""
    result = supabase.table("generation_traces").insert(row).execute()
    return str(result.data[0]["id"])


_SOURCE_COLUMNS = "id,topic,context,retrieved,retrieved_context,profile_snapshot,node_outputs"


def get_trace_sources(
    user_id: str,
    trace_id: str | None = None,
    post_id: int | None = None,
) -> dict[str, Any] | None:
    """What a post was generated from: the user's own trace, found by trace_id,
    else the newest trace linked to post_id. None if the user has no such trace
    (missing, or it belongs to someone else)."""
    if trace_id:
        rows = (
            supabase.table("generation_traces")
            .select(_SOURCE_COLUMNS)
            .eq("id", trace_id)
            .eq("user_id", user_id)
            .execute()
        ).data or []
        if rows:
            return rows[0]
    if post_id is not None:
        rows = (
            supabase.table("generation_traces")
            .select(_SOURCE_COLUMNS)
            .eq("post_id", post_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
        if rows:
            return rows[0]
    return None


def link_trace_to_post(trace_id: str, post_id: int, user_id: str) -> bool:
    """Set post_id on the user's own trace. False if no trace matched (missing or another user's)."""
    result = (
        supabase.table("generation_traces")
        .update({"post_id": post_id})
        .eq("id", trace_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data or []) > 0


def _update_node_outputs(
    trace_id: str,
    user_id: str,
    change: Callable[[dict[str, Any]], dict[str, Any]],
) -> bool:
    """Replace node_outputs on the user's own trace with change(current). False if no trace matched."""
    rows = (
        supabase.table("generation_traces")
        .select("node_outputs")
        .eq("id", trace_id)
        .eq("user_id", user_id)
        .execute()
    ).data or []
    if not rows:
        return False
    node_outputs = change(rows[0].get("node_outputs") or {})
    result = (
        supabase.table("generation_traces")
        .update({"node_outputs": node_outputs})
        .eq("id", trace_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data or []) > 0


def update_trace_fact_check(trace_id: str, user_id: str, record: dict[str, Any]) -> bool:
    """Set node_outputs.fact_check on the user's own trace. False if no trace matched."""
    return _update_node_outputs(trace_id, user_id, lambda current: {**current, "fact_check": record})


def append_trace_guard_entry(trace_id: str, user_id: str, entry: dict[str, Any]) -> bool:
    """Append one entry to node_outputs.specifics_guard on the user's own trace
    (a guard retry that happened after generation, e.g. a selection refine).
    False if no trace matched."""
    return _update_node_outputs(
        trace_id, user_id,
        lambda current: {**current, "specifics_guard": [*(current.get("specifics_guard") or []), entry]},
    )
