"""Publishing tables (migration 008): connected accounts and publish jobs.

Every query is scoped by user_id, except the three the worker and the webhooks
use, which act on jobs by id or provider reference: claim_due_jobs,
get_job_by_provider_ref and update_job. Those never take an id from a user.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from db.supabase_client import supabase
from publishing.types import AccountStatus, ConnectedAccount, ErrorCode, JobStatus

# A job left in "publishing" with no provider reference for this long was
# interrupted mid-call and is claimed again (its idempotency key makes that safe).
STALE_CLAIM_MINUTES = 10

_PENDING = (JobStatus.DRAFT.value, JobStatus.SCHEDULED.value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Provider tenant ----------------------------------------------------------

def get_publishing_ref(user_id: str, provider: str) -> str | None:
    """The provider's reference to this user, if they were created with `provider`."""
    rows = (
        supabase.table("accounts").select("publishing_provider,publishing_ref")
        .eq("user_id", user_id).execute()
    ).data or []
    if rows and rows[0].get("publishing_provider") == provider:
        return rows[0].get("publishing_ref")
    return None


def save_publishing_ref(user_id: str, provider: str, ref: str) -> None:
    supabase.table("accounts").upsert(
        {"user_id": user_id, "publishing_provider": provider, "publishing_ref": ref, "updated_at": _now()},
        on_conflict="user_id",
    ).execute()


# --- Connected accounts -------------------------------------------------------

def list_accounts(user_id: str, provider: str) -> list[dict[str, Any]]:
    """The user's accounts at this provider that have not been disconnected."""
    return (
        supabase.table("connected_accounts").select("*")
        .eq("user_id", user_id).eq("provider", provider)
        .neq("status", AccountStatus.DISCONNECTED.value)
        .order("created_at").execute()
    ).data or []


class AccountLimitError(ValueError):
    """Provider accounts exceed the one-account-per-platform entitlement."""


def sync_accounts(user_id: str, provider: str, current: list[ConnectedAccount]) -> list[dict[str, Any]]:
    """Make our rows match what the provider reports: add new accounts, update
    names and statuses, and mark ones it no longer lists as disconnected."""
    active = [account for account in current if account.status != AccountStatus.DISCONNECTED]
    if len({account.platform for account in active}) != len(active):
        raise AccountLimitError("Connect only one account per platform. Remove the extra account at your publishing provider and reconnect.")
    # Release stale platform slots before upserting replacement references, so
    # the unique per-platform index also permits legitimate reconnects.
    active_refs = {account.ref for account in active}
    for row in list_accounts(user_id, provider):
        if row["provider_account_ref"] not in active_refs:
            mark_account(user_id, row["id"], AccountStatus.DISCONNECTED)
    now = _now()
    for account in current:
        supabase.table("connected_accounts").upsert({
            "user_id": user_id,
            "provider": provider,
            "provider_account_ref": account.ref,
            "platform": account.platform.value,
            "display_name": account.display_name,
            "status": account.status.value,
            "updated_at": now,
        }, on_conflict="user_id,provider,provider_account_ref").execute()
    return list_accounts(user_id, provider)


def get_account(user_id: str, account_id: str) -> dict[str, Any] | None:
    rows = (
        supabase.table("connected_accounts").select("*")
        .eq("id", account_id).eq("user_id", user_id).execute()
    ).data or []
    return rows[0] if rows else None


def mark_account(user_id: str, account_id: str, status: AccountStatus) -> None:
    supabase.table("connected_accounts").update(
        {"status": status.value, "updated_at": _now()}
    ).eq("id", account_id).eq("user_id", user_id).execute()


# --- Publish jobs -------------------------------------------------------------

def create_job(
    user_id: str,
    *,
    provider: str,
    content: str,
    account_ids: list[str],
    post_id: int | None,
    scheduled_at: datetime | None,
    media: list[dict[str, Any]] | None = None,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """A scheduled job. With no scheduled_at it is due now."""
    due = (scheduled_at or datetime.now(timezone.utc)).isoformat()
    row = {
        "user_id": user_id,
        "provider": provider,
        "post_id": post_id,
        "approval_id": approval_id,
        "content": content,
        "media": media or [],
        "account_ids": account_ids,
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
        "next_attempt_at": due,
        "status": JobStatus.SCHEDULED.value,
        # One key for the life of the job: every attempt sends it to the provider.
        "idempotency_key": str(uuid.uuid4()),
        "attempts": 0,
        "results": [],
        "created_at": _now(),
    }
    return supabase.table("publish_jobs").insert(row).execute().data[0]


def list_jobs(user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    return (
        supabase.table("publish_jobs").select("*")
        .eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    ).data or []


def get_job(user_id: str, job_id: str) -> dict[str, Any] | None:
    rows = supabase.table("publish_jobs").select("*").eq("id", job_id).eq("user_id", user_id).execute().data or []
    return rows[0] if rows else None


def scheduled_times(user_id: str) -> list[datetime]:
    """When each of the user's waiting jobs is scheduled for. Jobs waiting to
    go out as soon as possible have no time and are left out."""
    rows = (
        supabase.table("publish_jobs").select("scheduled_at")
        .eq("user_id", user_id).eq("status", JobStatus.SCHEDULED.value).execute()
    ).data or []
    return [datetime.fromisoformat(row["scheduled_at"]) for row in rows if row.get("scheduled_at")]


def cancel_job(user_id: str, job_id: str) -> dict[str, Any] | None:
    """Cancel the user's own job if it has not started. Returns the cancelled
    row, or None when there is no such pending job (missing, another user's,
    or already publishing or finished)."""
    rows = (
        supabase.table("publish_jobs")
        .update({"status": JobStatus.CANCELLED.value, "updated_at": _now()})
        .eq("id", job_id).eq("user_id", user_id).in_("status", _PENDING).execute()
    ).data or []
    return rows[0] if rows else None


def cancel_pending_jobs(user_id: str, reason: ErrorCode) -> int:
    """Cancel every job of the user's that has not started; returns how many."""
    rows = (
        supabase.table("publish_jobs")
        .update({"status": JobStatus.CANCELLED.value, "error_code": reason.value, "updated_at": _now()})
        .eq("user_id", user_id).in_("status", _PENDING).execute()
    ).data or []
    return len(rows)


# --- Worker and webhooks (never called with an id from a user) -----------------

def claim_due_jobs(max_jobs: int) -> list[dict[str, Any]]:
    """Take up to max_jobs due jobs and mark them publishing, atomically
    (claim_publish_jobs in migration 008: FOR UPDATE SKIP LOCKED)."""
    return supabase.rpc(
        "claim_publish_jobs", {"max_jobs": max_jobs, "stale_minutes": STALE_CLAIM_MINUTES},
    ).execute().data or []


def list_unconfirmed_jobs(older_than: datetime, limit: int) -> list[dict[str, Any]]:
    """Jobs the provider accepted that have had no final status since older_than."""
    rows = (
        supabase.table("publish_jobs").select("*")
        .eq("status", JobStatus.PUBLISHING.value)
        .lt("updated_at", older_than.isoformat()).order("updated_at").limit(limit).execute()
    ).data or []
    return [row for row in rows if row.get("provider_post_ref")]


def get_job_by_provider_ref(provider: str, provider_post_ref: str) -> dict[str, Any] | None:
    rows = (
        supabase.table("publish_jobs").select("*")
        .eq("provider", provider).eq("provider_post_ref", provider_post_ref).execute()
    ).data or []
    return rows[0] if rows else None


def update_job(job_id: str, fields: dict[str, Any]) -> None:
    supabase.table("publish_jobs").update({**fields, "updated_at": _now()}).eq("id", job_id).execute()
