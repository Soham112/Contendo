"""What the publishing endpoints do: connect and list accounts, and create
jobs. Nothing here publishes: a job is only written to the queue, and the
worker (publishing.worker) sends it.
"""

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from memory import publish_store
from publishing import rules
from publishing.approval import matches_approval
from publishing.provider import PublishingProvider
from publishing.types import AccountStatus, EndUser, Platform

# "Add to queue" puts a post in the next free daily slot at this local time.
QUEUE_SLOT = time(hour=9)
# A scheduled time must be at least this far ahead, so it is not already past
# by the time the worker looks.
MIN_SCHEDULE_LEAD = timedelta(minutes=1)


class PublishRequestError(ValueError):
    """The request cannot become a job. `problems` are sentences for the user."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def ensure_end_user(user_id: str, provider: PublishingProvider) -> str:
    """The provider's reference to this user, creating their tenant on first use."""
    ref = publish_store.get_publishing_ref(user_id, provider.name)
    if ref:
        return ref
    ref = provider.create_end_user(EndUser(user_id=user_id))
    publish_store.save_publishing_ref(user_id, provider.name, ref)
    return ref


def refresh_accounts(user_id: str, provider: PublishingProvider) -> list[dict[str, Any]]:
    """The user's connected accounts, brought up to date with the provider.
    A user who has never connected anything has none, and no tenant is created."""
    ref = publish_store.get_publishing_ref(user_id, provider.name)
    if not ref:
        return []
    return publish_store.sync_accounts(user_id, provider.name, provider.list_connected_accounts(ref))


def disconnect(user_id: str, account_id: str, provider: PublishingProvider) -> bool:
    """Disconnect the user's own account. False when they have no such account."""
    account = publish_store.get_account(user_id, account_id)
    ref = publish_store.get_publishing_ref(user_id, provider.name)
    if not account or not ref or account["provider"] != provider.name:
        return False
    provider.disconnect_account(ref, account["provider_account_ref"])
    publish_store.mark_account(user_id, account_id, AccountStatus.DISCONNECTED)
    return True


def parse_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise PublishRequestError(["We couldn't read your time zone. Reload the page and try again."]) from exc


def next_queue_slot(user_id: str, tz: ZoneInfo, now: datetime | None = None) -> datetime:
    """The next free queue slot: QUEUE_SLOT local time on the first day, from
    today on, when that time is still ahead and the user has nothing scheduled."""
    now = now or datetime.now(timezone.utc)
    local_now = now.astimezone(tz)
    taken = {when.astimezone(tz).date() for when in publish_store.scheduled_times(user_id)}
    day = local_now.date()
    while True:
        slot = datetime.combine(day, QUEUE_SLOT, tzinfo=tz)
        if slot > local_now + MIN_SCHEDULE_LEAD and day not in taken:
            return slot.astimezone(timezone.utc)
        day += timedelta(days=1)


def create_job(
    user_id: str,
    provider: PublishingProvider,
    *,
    content: str,
    account_ids: list[str],
    post_id: int | None,
    media: list[dict[str, Any]],
    when: str,                       # "now" | "schedule" | "queue"
    scheduled_at: datetime | None,   # for "schedule": timezone-aware
    tz_name: str,
    approval_id: str | None = None,
) -> dict[str, Any]:
    """Validate against each target platform's rules and queue the job.
    Raises PublishRequestError with every problem found."""
    problems: list[str] = []
    if not content.strip():
        problems.append("There is nothing to publish yet.")
    if not account_ids:
        problems.append("Choose at least one account to publish to.")

    accounts = {row["id"]: row for row in publish_store.list_accounts(user_id, provider.name)}
    for account_id in dict.fromkeys(account_ids):
        account = accounts.get(account_id)
        if account is None:
            problems.append("One of the chosen accounts is no longer connected. Reload and choose again.")
            continue
        if account["status"] != AccountStatus.CONNECTED.value:
            problems.append(f"Reconnect {rules.label(account['platform'])} before publishing to it.")
            continue
        problems += rules.problems(Platform(account["platform"]), content, media)

    run_at: datetime | None = None
    if when == "schedule":
        if scheduled_at is None or scheduled_at.tzinfo is None:
            problems.append("Choose a date and time.")
        elif scheduled_at <= datetime.now(timezone.utc) + MIN_SCHEDULE_LEAD:
            problems.append("Choose a time in the future.")
        else:
            run_at = scheduled_at.astimezone(timezone.utc)
    elif when == "queue":
        run_at = next_queue_slot(user_id, parse_timezone(tz_name))
    elif when != "now":
        problems.append("Choose when to publish.")

    if problems:
        raise PublishRequestError(list(dict.fromkeys(problems)))
    if not matches_approval(user_id, approval_id, content, media, post_id):
        raise PublishRequestError(["Read and approve this exact text, resolving each claim flag, before publishing or scheduling."])
    return publish_store.create_job(
        user_id, provider=provider.name, content=content, account_ids=list(dict.fromkeys(account_ids)),
        post_id=post_id, scheduled_at=run_at, media=media, approval_id=approval_id,
    )
