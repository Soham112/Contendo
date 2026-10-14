"""An in-memory provider for tests and local development.

It behaves like a real provider from the app's side: tenants, a connect step,
accounts, idempotent publishes and statuses. Nothing leaves the process, and
its state is lost on restart.

Local development: its connect URL is the redirect URL itself, with the account
already connected, so "Connect Instagram" works with no third party.

Tests script failures with fail_next_publish() and set_account_status().
"""

import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit

from publishing.types import (
    AccountResult, AccountStatus, ConnectedAccount, EndUser, JobStatus, MediaItem, Platform,
    PostContent, ProviderError, PublishStatus, StatusUpdate,
)


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.users: dict[str, str] = {}                           # our user_id -> provider ref
        self.accounts: dict[str, dict[str, ConnectedAccount]] = {}  # provider ref -> account ref -> account
        self.publishes: dict[str, dict] = {}                      # provider post ref -> record
        self.by_idempotency_key: dict[str, str] = {}
        self.publish_calls: list[dict] = []
        self._publish_errors: list[ProviderError] = []

    # --- test controls ------------------------------------------------------
    def fail_next_publish(self, error: ProviderError) -> None:
        self._publish_errors.append(error)

    def set_account_status(self, provider_user_ref: str, account_ref: str, status: AccountStatus) -> None:
        account = self.accounts[provider_user_ref][account_ref]
        self.accounts[provider_user_ref][account_ref] = ConnectedAccount(
            account.ref, account.platform, account.display_name, status)

    def set_status(self, provider_post_ref: str, status: PublishStatus) -> None:
        self.publishes[provider_post_ref]["status"] = status

    # --- PublishingProvider -------------------------------------------------
    def create_end_user(self, user: EndUser) -> str:
        ref = self.users.setdefault(user.user_id, f"fake-user-{user.user_id}")
        self.accounts.setdefault(ref, {})
        return ref

    def get_connect_url(self, provider_user_ref: str, platform: Platform, redirect_url: str) -> str:
        account_ref = f"fake-{platform.value}-{uuid.uuid4().hex[:8]}"
        self.accounts.setdefault(provider_user_ref, {})[account_ref] = ConnectedAccount(
            ref=account_ref, platform=platform, display_name=f"Test {platform.value} account")
        parts = urlsplit(redirect_url)
        query = "&".join(part for part in (parts.query, urlencode({"connect_status": "success"})) if part)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

    def list_connected_accounts(self, provider_user_ref: str) -> list[ConnectedAccount]:
        return list(self.accounts.get(provider_user_ref, {}).values())

    def disconnect_account(self, provider_user_ref: str, account_ref: str) -> None:
        self.accounts.get(provider_user_ref, {}).pop(account_ref, None)

    def upload_media(self, provider_user_ref: str, filename: str, content_type: str, data: bytes) -> MediaItem:
        kind = "video" if content_type.startswith("video/") else "image"
        return MediaItem(ref=f"fake-media://{uuid.uuid4().hex}/{filename}", kind=kind)

    def publish(
        self,
        provider_user_ref: str,
        post: PostContent,
        account_refs: list[str],
        schedule_at: datetime | None,
        *,
        idempotency_key: str,
    ) -> str:
        self.publish_calls.append({"user": provider_user_ref, "post": post, "accounts": list(account_refs),
                                   "schedule_at": schedule_at, "idempotency_key": idempotency_key})
        if idempotency_key in self.by_idempotency_key:
            return self.by_idempotency_key[idempotency_key]
        if self._publish_errors:
            raise self._publish_errors.pop(0)
        ref = f"fake-post-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        status = PublishStatus(
            JobStatus.PUBLISHED if schedule_at is None else JobStatus.SCHEDULED,
            tuple(AccountResult(account_ref, JobStatus.PUBLISHED, url=f"https://example.invalid/{ref}/{account_ref}")
                  for account_ref in account_refs) if schedule_at is None else (),
            published_at=now if schedule_at is None else None,
        )
        self.publishes[ref] = {"status": status, "user": provider_user_ref}
        self.by_idempotency_key[idempotency_key] = ref
        return ref

    def get_status(self, provider_post_ref: str) -> PublishStatus:
        return self.publishes[provider_post_ref]["status"]

    def cancel(self, provider_post_ref: str) -> None:
        self.publishes[provider_post_ref]["status"] = PublishStatus(JobStatus.CANCELLED)

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> StatusUpdate | None:
        """Body: {"provider_post_ref": ..., "status": "published" | "failed"}, with
        the header X-Fake-Signature: valid."""
        if headers.get("x-fake-signature") != "valid":
            raise PermissionError("fake webhook signature mismatch")
        payload = json.loads(body)
        ref = payload.get("provider_post_ref")
        if not ref:
            return None
        return StatusUpdate(ref, PublishStatus(JobStatus(payload["status"])))


# One instance per process, so a connect in one request is seen by the next.
fake_provider = FakeProvider()
