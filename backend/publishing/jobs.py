"""Running publish jobs: one attempt, what its outcome does to the job, and
retries. Called by the worker and the provider webhook, never inside a user's
request.

A job is retried when the provider says the failure may pass (network, rate
limit, outage): after BACKOFF_BASE_SECONDS, then twice that, and so on, up to
MAX_ATTEMPTS attempts. Every attempt sends the job's idempotency key, so an
attempt whose answer was lost cannot post a second time.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from billing.entitlements import get_entitlements
from memory import publish_store
from memory.feedback_store import mark_published
from publishing.provider import PublishingProvider
from publishing.rules import label
from publishing.types import (
    AccountStatus, ErrorCode, JobStatus, MediaItem, PostContent, ProviderError, PublishStatus,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BACKOFF_BASE_SECONDS = 60
# How long a job waits before it is looked at again while publishing is paused.
PAUSED_RECHECK = timedelta(hours=1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def backoff(attempts: int) -> timedelta:
    """The wait after a failed attempt number `attempts` (1-based): 1, 2, 4, 8 minutes."""
    return timedelta(seconds=BACKOFF_BASE_SECONDS * 2 ** (attempts - 1))


def _fail(job: dict[str, Any], code: ErrorCode, message: str = "", results: list[dict] | None = None) -> None:
    logger.warning("publish job %s failed: %s %s", job["id"], code.value, message)
    publish_store.update_job(job["id"], {
        "status": JobStatus.FAILED.value, "error_code": code.value, "error_message": message[:500],
        **({"results": results} if results is not None else {}),
    })


def _retry_or_fail(job: dict[str, Any], error: ProviderError) -> None:
    if error.retryable and job["attempts"] < MAX_ATTEMPTS:
        publish_store.update_job(job["id"], {
            "status": JobStatus.SCHEDULED.value,
            "next_attempt_at": (_now() + backoff(job["attempts"])).isoformat(),
            "error_code": error.code.value, "error_message": str(error)[:500],
        })
        return
    _fail(job, error.code, str(error))


def _pause(job: dict[str, Any]) -> None:
    """Hand the job back unpublished and unpenalised: the user cannot publish
    right now (payment failed). It goes out when they can, or is cancelled when
    the subscription ends (billing.webhooks)."""
    publish_store.update_job(job["id"], {
        "status": JobStatus.SCHEDULED.value,
        "attempts": max(job["attempts"] - 1, 0),
        "next_attempt_at": (_now() + PAUSED_RECHECK).isoformat(),
        "error_code": ErrorCode.PAYMENT_REQUIRED.value,
    })


def apply_status(job: dict[str, Any], status: PublishStatus, accounts: list[dict[str, Any]]) -> None:
    """Record what the provider says happened. `accounts` are the user's
    connected_accounts rows, to turn the provider's account references into ours."""
    if status.status not in (JobStatus.PUBLISHED, JobStatus.FAILED, JobStatus.CANCELLED):
        return  # still in progress: nothing to record yet
    by_ref = {row["provider_account_ref"]: row for row in accounts}
    results = [
        {
            "account_id": (by_ref.get(result.account_ref) or {}).get("id"),
            "platform": (by_ref.get(result.account_ref) or {}).get("platform"),
            "status": result.status.value,
            "url": result.url,
            "error_code": result.error_code.value if result.error_code else None,
        }
        for result in status.accounts
    ]
    if status.status == JobStatus.CANCELLED:
        publish_store.update_job(job["id"], {"status": JobStatus.CANCELLED.value, "results": results})
        return
    if status.status == JobStatus.FAILED:
        failed = [result for result in status.accounts if result.status == JobStatus.FAILED]
        for result in failed:
            row = by_ref.get(result.account_ref)
            if row and result.error_code == ErrorCode.RECONNECT_REQUIRED:
                publish_store.mark_account(job["user_id"], row["id"], AccountStatus.NEEDS_RECONNECT)
        first = failed[0] if failed else None
        _fail(job, (first.error_code if first else None) or ErrorCode.UNKNOWN,
              first.error_message if first else "", results)
        return
    publish_store.update_job(job["id"], {
        "status": JobStatus.PUBLISHED.value,
        "published_at": (status.published_at or _now()).isoformat(),
        "results": results, "error_code": None, "error_message": None,
    })
    if job.get("post_id") is not None:
        # The post's own "published" mark, which History already shows.
        platforms = ", ".join(sorted({label(r["platform"]) for r in results if r["platform"]}))
        mark_published(job["post_id"], platforms, job["content"], user_id=job["user_id"])


def process_job(job: dict[str, Any], provider: PublishingProvider) -> None:
    """One attempt at a job the worker has claimed (status "publishing")."""
    user_id = job["user_id"]
    if not get_entitlements(user_id).can_publish:
        _pause(job)
        return
    provider_user_ref = publish_store.get_publishing_ref(user_id, provider.name)
    accounts = publish_store.list_accounts(user_id, provider.name)
    by_id = {row["id"]: row for row in accounts}
    targets = [by_id.get(account_id) for account_id in job["account_ids"]]
    if not provider_user_ref or not targets or any(target is None for target in targets):
        _fail(job, ErrorCode.ACCOUNT_REMOVED)
        return
    if any(target["status"] != AccountStatus.CONNECTED.value for target in targets):
        _fail(job, ErrorCode.RECONNECT_REQUIRED)
        return
    post = PostContent(job["content"], tuple(MediaItem(item["ref"], item["kind"]) for item in job.get("media") or []))
    try:
        ref = provider.publish(
            provider_user_ref, post, [target["provider_account_ref"] for target in targets], None,
            idempotency_key=str(job["idempotency_key"]),
        )
        publish_store.update_job(job["id"], {"provider_post_ref": ref, "error_code": None, "error_message": None})
        status = provider.get_status(ref)
    except ProviderError as error:
        _retry_or_fail(job, error)
        return
    apply_status({**job, "provider_post_ref": ref}, status, accounts)


def confirm_job(job: dict[str, Any], provider: PublishingProvider) -> None:
    """Ask the provider what became of a job it accepted (the webhook's backstop)."""
    try:
        status = provider.get_status(job["provider_post_ref"])
    except ProviderError as error:
        logger.warning("publish job %s: status check failed: %s", job["id"], error)
        return
    apply_status(job, status, publish_store.list_accounts(job["user_id"], provider.name))
