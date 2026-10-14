"""The publishing provider interface, and which provider is in use.

Everything outside this package publishes through PublishingProvider. The
third-party provider behind it is a deliberate dependency, not the end state:
a DirectProvider using our own platform apps (docs/publishing-roadmap.md)
replaces it by implementing this one protocol.

PUBLISHING_PROVIDER picks the provider: "fake" (tests and local development)
or "zernio". There is no default: a server with publishing misconfigured must
say so rather than quietly pretend to publish.
"""

import os
from datetime import datetime
from typing import Protocol

from config import security
from publishing.types import (
    ConnectedAccount, EndUser, MediaItem, Platform, PostContent, PublishStatus, StatusUpdate,
)

PROVIDER_ENV = "PUBLISHING_PROVIDER"


class PublishingConfigError(RuntimeError):
    """PUBLISHING_PROVIDER is missing, unknown, or lacks its own settings."""


class PublishingProvider(Protocol):
    # Stored with every reference this provider hands out (accounts.publishing_provider,
    # connected_accounts.provider, publish_jobs.provider).
    name: str

    def create_end_user(self, user: EndUser) -> str:
        """Create this provider's tenant for one of our users; returns its
        reference. Calling it again for the same user returns the same one."""

    def get_connect_url(self, provider_user_ref: str, platform: Platform, redirect_url: str) -> str:
        """Where to send the user's browser to connect one account on `platform`.
        They come back to redirect_url when done."""

    def list_connected_accounts(self, provider_user_ref: str) -> list[ConnectedAccount]:
        """Every account the user has connected, with its current status."""

    def disconnect_account(self, provider_user_ref: str, account_ref: str) -> None:
        """Remove one connected account at the provider."""

    def upload_media(self, provider_user_ref: str, filename: str, content_type: str, data: bytes) -> MediaItem:
        """Store a file with the provider for use in a later publish."""

    def publish(
        self,
        provider_user_ref: str,
        post: PostContent,
        account_refs: list[str],
        schedule_at: datetime | None,
        *,
        idempotency_key: str,
    ) -> str:
        """Publish `post` to those accounts, now or at schedule_at; returns the
        provider's reference to the publish. A second call with the same
        idempotency_key must not post again: it returns the first reference."""

    def get_status(self, provider_post_ref: str) -> PublishStatus:
        """The current state of one publish."""

    def cancel(self, provider_post_ref: str) -> None:
        """Stop a publish that has not gone out yet."""

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> StatusUpdate | None:
        """Verify and read a webhook from this provider. Returns the status it
        carries, or None for an event that is not about a publish. Raises
        PermissionError when the signature does not verify."""


def provider_name() -> str:
    return os.environ.get(PROVIDER_ENV, "").strip().lower()


def get_provider() -> PublishingProvider:
    """The configured provider. Raises PublishingConfigError when there is none."""
    name = provider_name()
    if name == "fake":
        if security.current().environment == "production":
            raise PublishingConfigError(f"{PROVIDER_ENV}=fake cannot run in production: nothing would be published.")
        from publishing.fake import fake_provider
        return fake_provider
    if name == "zernio":
        from publishing.zernio import ZernioProvider
        return ZernioProvider.from_env()
    raise PublishingConfigError(
        f"{PROVIDER_ENV} must be 'fake' or 'zernio' (got {name!r}). Publishing is unavailable."
    )
