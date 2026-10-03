from typing import Any

from db.supabase_client import supabase


def save_generation_trace(row: dict[str, Any]) -> str:
    """Insert one generation_traces row (row must include user_id); return its id."""
    result = supabase.table("generation_traces").insert(row).execute()
    return str(result.data[0]["id"])


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


def update_trace_fact_check(trace_id: str, user_id: str, record: dict[str, Any]) -> bool:
    """Set node_outputs.fact_check on the user's own trace. False if no trace matched."""
    rows = (
        supabase.table("generation_traces")
        .select("node_outputs")
        .eq("id", trace_id)
        .eq("user_id", user_id)
        .execute()
    ).data or []
    if not rows:
        return False
    node_outputs = {**(rows[0].get("node_outputs") or {}), "fact_check": record}
    result = (
        supabase.table("generation_traces")
        .update({"node_outputs": node_outputs})
        .eq("id", trace_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data or []) > 0
