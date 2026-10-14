"""Contendo's own publishing types.

Nothing here mirrors a provider's response: each adapter in this package maps
its provider's shapes to and from these, so the rest of the app never sees one.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Platform(str, Enum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    GOOGLE_BUSINESS = "google_business"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    X = "x"


class AccountStatus(str, Enum):
    CONNECTED = "connected"
    NEEDS_RECONNECT = "needs_reconnect"
    DISCONNECTED = "disconnected"


class JobStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorCode(str, Enum):
    """Why a publish failed, as something the user can act on. Stored in
    publish_jobs.error_code; publishing.messages turns it into words."""
    RECONNECT_REQUIRED = "reconnect_required"      # the platform no longer accepts our access
    CONTENT_REJECTED = "content_rejected"          # the platform refused this post
    DUPLICATE = "duplicate"                        # the platform already has this post
    PLATFORM_LIMIT = "platform_limit"              # the account has hit the platform's posting limit
    ACCOUNT_REMOVED = "account_removed"            # the target account is no longer connected
    PAYMENT_REQUIRED = "payment_required"          # publishing is paused until the plan is paid
    SUBSCRIPTION_ENDED = "subscription_ended"      # cancelled because the plan ended
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # we could not reach the publishing service
    APPROVAL_REQUIRED = "approval_required"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConnectedAccount:
    """One social account at the provider. `ref` is the provider's id for it."""
    ref: str
    platform: Platform
    display_name: str
    status: AccountStatus = AccountStatus.CONNECTED


@dataclass(frozen=True)
class MediaItem:
    """Media already uploaded to the provider. `ref` is what it gave back."""
    ref: str
    kind: str  # "image" | "video"


@dataclass(frozen=True)
class PostContent:
    text: str
    media: tuple[MediaItem, ...] = ()


@dataclass(frozen=True)
class AccountResult:
    """How one target account's publish went."""
    account_ref: str
    status: JobStatus  # PUBLISHING, PUBLISHED or FAILED
    url: str = ""
    error_code: ErrorCode | None = None
    error_message: str = ""


@dataclass(frozen=True)
class PublishStatus:
    """A publish as the provider reports it. PUBLISHED means every account
    published; FAILED means at least one did not (see `accounts`)."""
    status: JobStatus
    accounts: tuple[AccountResult, ...] = ()
    published_at: datetime | None = None


@dataclass(frozen=True)
class StatusUpdate:
    """A status pushed by the provider's webhook, for the publish it names."""
    provider_post_ref: str
    status: PublishStatus


class ProviderError(Exception):
    """A provider call failed. `code` says why; `retryable` says whether the
    same call may succeed later."""

    def __init__(self, code: ErrorCode, message: str = "", *, retryable: bool = False):
        super().__init__(message or code.value)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class EndUser:
    """What a provider needs to create its tenant for one of our users."""
    user_id: str
    display_name: str = ""
    extra: dict = field(default_factory=dict)
