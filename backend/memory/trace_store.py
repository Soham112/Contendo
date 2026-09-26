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
