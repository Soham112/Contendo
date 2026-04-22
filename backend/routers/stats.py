from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth.clerk import get_user_id_dep
from db.supabase_client import supabase
from memory.vector_store import get_all_tags, get_total_chunks

router = APIRouter()


class StatsResponse(BaseModel):
    total_chunks: int
    tags: list[str]


@router.get("/stats", response_model=StatsResponse)
async def stats(user_id: str = Depends(get_user_id_dep)) -> StatsResponse:
    return StatsResponse(
        total_chunks=get_total_chunks(user_id=user_id),
        tags=get_all_tags(user_id=user_id),
    )


# ── Usage ─────────────────────────────────────────────────────────────────────


class UsageBreakdownItem(BaseModel):
    event_type: str
    calls: int
    cost_usd: float


class UsageMeResponse(BaseModel):
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    calls_this_week: int
    cost_this_week: float
    breakdown: list[UsageBreakdownItem]


@router.get("/usage/me", response_model=UsageMeResponse)
async def usage_me(user_id: str = Depends(get_user_id_dep)) -> UsageMeResponse:
    rows = (
        supabase.table("usage_events")
        .select("event_type,input_tokens,output_tokens,estimated_cost_usd,created_at")
        .eq("user_id", user_id)
        .execute()
        .data
    )

    now = datetime.now(timezone.utc)
    week_since = (now - timedelta(days=7)).isoformat()

    total_calls = len(rows)
    total_input = sum(r.get("input_tokens") or 0 for r in rows)
    total_output = sum(r.get("output_tokens") or 0 for r in rows)
    total_cost = sum(float(r.get("estimated_cost_usd") or 0) for r in rows)

    week_rows = [r for r in rows if r["created_at"] >= week_since]
    calls_this_week = len(week_rows)
    cost_this_week = sum(float(r.get("estimated_cost_usd") or 0) for r in week_rows)

    # Breakdown by event_type
    by_type: dict[str, dict] = {}
    for r in rows:
        et = r.get("event_type") or "unknown"
        if et not in by_type:
            by_type[et] = {"calls": 0, "cost": 0.0}
        by_type[et]["calls"] += 1
        by_type[et]["cost"] += float(r.get("estimated_cost_usd") or 0)

    breakdown = [
        UsageBreakdownItem(
            event_type=et,
            calls=d["calls"],
            cost_usd=round(d["cost"], 6),
        )
        for et, d in sorted(by_type.items())
    ]

    return UsageMeResponse(
        total_calls=total_calls,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_cost_usd=round(total_cost, 6),
        calls_this_week=calls_this_week,
        cost_this_week=round(cost_this_week, 6),
        breakdown=breakdown,
    )
