"""Billing tables (migration 009): subscriptions, handled Stripe events, and
monthly generation counts.

subscriptions.status is written here only by billing.webhooks, from a
subscription fetched from Stripe. Nothing the browser sends reaches it.
"""

from datetime import datetime, timezone
from typing import Any

from db.supabase_client import supabase

_SUBSCRIPTION_COLUMNS = (
    "user_id,stripe_customer_id,stripe_subscription_id,status,price_id,"
    "current_period_end,trial_end,cancel_at_period_end"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_period(now: datetime | None = None) -> str:
    """The quota period: the calendar month, in UTC, as 'YYYY-MM'."""
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


# --- Subscriptions ------------------------------------------------------------

def get_subscription(user_id: str) -> dict[str, Any] | None:
    rows = supabase.table("subscriptions").select(_SUBSCRIPTION_COLUMNS).eq("user_id", user_id).execute().data or []
    return rows[0] if rows else None


def get_user_id_for_customer(stripe_customer_id: str) -> str | None:
    """The user a Stripe customer belongs to. A lookup by Stripe's id, for
    webhooks: the customer id comes from a verified Stripe event."""
    rows = (
        supabase.table("subscriptions").select("user_id")
        .eq("stripe_customer_id", stripe_customer_id).execute()
    ).data or []
    return rows[0]["user_id"] if rows else None


def save_customer(user_id: str, stripe_customer_id: str) -> None:
    supabase.table("subscriptions").upsert(
        {"user_id": user_id, "stripe_customer_id": stripe_customer_id, "updated_at": _now()},
        on_conflict="user_id",
    ).execute()


def save_subscription(user_id: str, fields: dict[str, Any]) -> None:
    """Store a subscription as Stripe reports it (billing.webhooks only)."""
    supabase.table("subscriptions").upsert(
        {"user_id": user_id, **fields, "updated_at": _now()}, on_conflict="user_id",
    ).execute()


# --- Stripe events ------------------------------------------------------------

def claim_event(event_id: str, event_type: str) -> bool:
    """Record a Stripe event as handled. False when it already was: the
    primary key on event_id makes a redelivery a no-op."""
    result = supabase.table("stripe_events").upsert(
        {"event_id": event_id, "type": event_type}, on_conflict="event_id", ignore_duplicates=True,
    ).execute()
    return bool(result.data)


def release_event(event_id: str) -> None:
    """Forget an event whose handling failed, so Stripe's retry is processed."""
    supabase.table("stripe_events").delete().eq("event_id", event_id).execute()


# --- Generation usage ---------------------------------------------------------

def get_generation_count(user_id: str, period: str) -> int:
    rows = (
        supabase.table("generation_usage").select("count")
        .eq("user_id", user_id).eq("period", period).execute()
    ).data or []
    return int(rows[0]["count"]) if rows else 0


def reserve_generation(user_id: str, period: str, limit: int | None) -> bool:
    """Count one generation if that stays within limit (None: no limit).
    Atomic in the database, so two requests at the limit cannot both pass."""
    result = supabase.rpc(
        "reserve_generation", {"p_user_id": user_id, "p_period": period, "max_count": limit},
    ).execute()
    return bool(result.data)


def release_generation(user_id: str, period: str) -> None:
    """Give back a reserved generation that produced no post."""
    supabase.rpc("release_generation", {"p_user_id": user_id, "p_period": period}).execute()
