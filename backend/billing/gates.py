"""The HTTP side of entitlements: one place that turns "your plan does not
allow this" into a 402 the frontend can act on. Routers call these; they never
read a plan themselves.

Every 402 carries detail = {code, message, entitlements}:
  quota_exceeded    the month's generations are used up
  upgrade_required  the plan has no publishing or no room for another account
  payment_required  a pro user's payment failed; publishing is paused
"""

from fastapi import HTTPException

from billing.entitlements import PLAN_FREE, Entitlements, get_entitlements


def _refuse(code: str, message: str, entitlements: Entitlements) -> None:
    raise HTTPException(status_code=402, detail={
        "code": code, "message": message, "entitlements": entitlements.to_dict(),
    })


def _refuse_publishing(entitlements: Entitlements) -> None:
    if entitlements.publishing_paused:
        _refuse("payment_required",
                "Publishing is paused because your last payment didn't go through. "
                "Update your payment method to carry on.", entitlements)
    _refuse("upgrade_required", "Publishing and scheduling are part of the Pro plan.", entitlements)


def require_publishing(user_id: str) -> Entitlements:
    entitlements = get_entitlements(user_id)
    if not entitlements.can_publish:
        _refuse_publishing(entitlements)
    return entitlements


def require_account_slot(user_id: str, connected: int) -> Entitlements:
    """May this user connect one more account, given how many they have on this platform?"""
    entitlements = get_entitlements(user_id)
    if not entitlements.can_publish:
        _refuse_publishing(entitlements)
    if connected >= entitlements.max_accounts_per_platform:
        _refuse("upgrade_required",
                f"Your plan includes {entitlements.max_accounts_per_platform} account per platform. "
                "Disconnect one to add another.", entitlements)
    return entitlements


def quota_exceeded(entitlements: Entitlements) -> HTTPException:
    """The 402 for a user with no generations left this month."""
    if entitlements.plan == PLAN_FREE:
        message = (f"You've used all {entitlements.generation_limit} free posts for this month. "
                   "Upgrade to Pro to keep going, or come back next month.")
    else:
        message = (f"You've reached this month's limit of {entitlements.generation_limit} posts. "
                   "It resets at the start of next month.")
    return HTTPException(status_code=402, detail={
        "code": "quota_exceeded", "message": message, "entitlements": entitlements.to_dict(),
    })
