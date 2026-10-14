"""What a user's plan allows. Every gated endpoint asks get_entitlements();
nothing else in the backend compares a plan or a subscription status.

Plans:
  free  10 generated posts a calendar month; no connected accounts, no publishing.
  pro   PRO_GENERATIONS_PER_MONTH posts; connected accounts, publishing, scheduling.

A subscription that is trialing or active is pro. One that is past_due is in
Stripe's grace period (Stripe is retrying the payment): the user keeps their
generation limit and their connected accounts, but publishing is paused until
the payment succeeds. Any other status, or none, is free.
"""

from dataclasses import asdict, dataclass

from memory.billing_store import current_period, get_generation_count, get_subscription

PLAN_FREE = "free"
PLAN_PRO = "pro"

FREE_GENERATIONS_PER_MONTH = 10
# Pro includes 300 generated posts and one connected account per platform.
PRO_GENERATIONS_PER_MONTH = 300
PRO_MAX_ACCOUNTS_PER_PLATFORM = 1

# Stripe subscription statuses.
_PAID = frozenset({"trialing", "active"})
_GRACE = frozenset({"past_due"})
# The subscription is over: pending scheduled posts are cancelled (billing.webhooks).
ENDED_STATUSES = frozenset({"canceled", "unpaid", "incomplete_expired"})


@dataclass(frozen=True)
class Entitlements:
    plan: str
    subscription_status: str | None
    generation_limit: int
    generations_used: int
    generations_remaining: int
    can_generate: bool
    can_publish: bool
    # True in Stripe's grace period: a pro user whose payment failed.
    publishing_paused: bool
    max_accounts_per_platform: int
    trial_end: str | None
    current_period_end: str | None
    cancel_at_period_end: bool
    # The quota period this count is for, 'YYYY-MM' (UTC).
    period: str

    def to_dict(self) -> dict:
        return asdict(self)


def get_entitlements(user_id: str) -> Entitlements:
    subscription = get_subscription(user_id) or {}
    status = subscription.get("status")
    paid, grace = status in _PAID, status in _GRACE
    pro = paid or grace
    limit = PRO_GENERATIONS_PER_MONTH if pro else FREE_GENERATIONS_PER_MONTH
    period = current_period()
    used = get_generation_count(user_id, period)
    return Entitlements(
        plan=PLAN_PRO if pro else PLAN_FREE,
        subscription_status=status,
        generation_limit=limit,
        generations_used=used,
        generations_remaining=max(limit - used, 0),
        can_generate=used < limit,
        can_publish=paid,
        publishing_paused=grace,
        max_accounts_per_platform=PRO_MAX_ACCOUNTS_PER_PLATFORM if pro else 0,
        trial_end=subscription.get("trial_end") if status == "trialing" else None,
        current_period_end=subscription.get("current_period_end") if pro else None,
        cancel_at_period_end=bool(subscription.get("cancel_at_period_end")) if pro else False,
        period=period,
    )
