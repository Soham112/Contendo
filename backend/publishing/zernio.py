"""Zernio adapter (https://docs.zernio.com), written from its OpenAPI spec of
2026-10-13. One Zernio profile per Contendo user, with our user id as its
externalId; the user's accounts live inside that profile.

Not yet run against a live Zernio account: see docs/publishing-roadmap.md for
the sandbox check to do before this is switched on.

Settings: ZERNIO_API_KEY, and ZERNIO_WEBHOOK_SECRET (the secret set on the
webhook endpoint in Zernio; deliveries are signed with it).
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from publishing.provider import PublishingConfigError
from publishing.types import (
    AccountResult, AccountStatus, ConnectedAccount, EndUser, ErrorCode, JobStatus, MediaItem,
    Platform, PostContent, ProviderError, PublishStatus, StatusUpdate,
)

BASE_URL = "https://zernio.com/api/v1"
TIMEOUT_SECONDS = 30

# Our platform -> Zernio's slug (the enum of GET /v1/connect/{platform}).
_SLUGS: dict[Platform, str] = {
    Platform.INSTAGRAM: "instagram",
    Platform.FACEBOOK: "facebook",
    Platform.LINKEDIN: "linkedin",
    Platform.GOOGLE_BUSINESS: "googlebusiness",
    Platform.TIKTOK: "tiktok",
    Platform.YOUTUBE: "youtube",
    Platform.X: "twitter",
}
_PLATFORMS: dict[str, Platform] = {slug: platform for platform, slug in _SLUGS.items()}

# Zernio's errorCategory (its full enum) -> ours.
_ERROR_CODES: dict[str, ErrorCode] = {
    "auth_expired": ErrorCode.RECONNECT_REQUIRED,
    "account_issue": ErrorCode.RECONNECT_REQUIRED,
    "user_content": ErrorCode.CONTENT_REJECTED,
    "user_abuse": ErrorCode.CONTENT_REJECTED,
    "platform_rejected": ErrorCode.CONTENT_REJECTED,
    "platform_rate_limit": ErrorCode.PLATFORM_LIMIT,
    "quota_exhausted": ErrorCode.PLATFORM_LIMIT,
    "platform_error": ErrorCode.PROVIDER_UNAVAILABLE,
    "system_error": ErrorCode.PROVIDER_UNAVAILABLE,
    "unknown": ErrorCode.UNKNOWN,
}

# Zernio's post status -> ours. "partial" (some accounts failed) is a failure
# here; the per-account results say which.
_POST_STATUS: dict[str, JobStatus] = {
    "draft": JobStatus.DRAFT,
    "scheduled": JobStatus.SCHEDULED,
    "publishing": JobStatus.PUBLISHING,
    "published": JobStatus.PUBLISHED,
    "partial": JobStatus.FAILED,
    "failed": JobStatus.FAILED,
    "cancelled": JobStatus.CANCELLED,
}
_TARGET_STATUS: dict[str, JobStatus] = {
    "published": JobStatus.PUBLISHED,
    "failed": JobStatus.FAILED,
    "cancelled": JobStatus.CANCELLED,
}

_POST_EVENTS = frozenset({"post.published", "post.failed", "post.partial", "post.cancelled"})
_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _account_ref(target: dict[str, Any]) -> str:
    """A target's account id: a string in webhooks, an embedded account on GET."""
    account = target.get("accountId")
    return str(account.get("_id", "")) if isinstance(account, dict) else str(account or "")


def _status_from_post(post: dict[str, Any]) -> PublishStatus:
    accounts = []
    for target in post.get("platforms") or []:
        status = _TARGET_STATUS.get(target.get("status", ""), JobStatus.PUBLISHING)
        failed = status == JobStatus.FAILED
        accounts.append(AccountResult(
            account_ref=_account_ref(target),
            status=status,
            url=target.get("publishedUrl") or target.get("platformPostUrl") or "",
            error_code=_ERROR_CODES.get(target.get("errorCategory") or "unknown", ErrorCode.UNKNOWN) if failed else None,
            error_message=(target.get("error") or target.get("errorMessage") or "") if failed else "",
        ))
    return PublishStatus(
        status=_POST_STATUS.get(post.get("status", ""), JobStatus.PUBLISHING),
        accounts=tuple(accounts),
        published_at=_parse_time(post.get("publishedAt")),
    )


_instances: dict[tuple[str, str], "ZernioProvider"] = {}


class ZernioProvider:
    name = "zernio"

    def __init__(self, api_key: str, webhook_secret: str, client: httpx.Client | None = None):
        self._webhook_secret = webhook_secret
        self._client = client or httpx.Client(
            base_url=BASE_URL, timeout=TIMEOUT_SECONDS,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @classmethod
    def from_env(cls) -> "ZernioProvider":
        api_key = os.environ.get("ZERNIO_API_KEY", "").strip()
        webhook_secret = os.environ.get("ZERNIO_WEBHOOK_SECRET", "").strip()
        if not api_key or not webhook_secret:
            raise PublishingConfigError("ZERNIO_API_KEY and ZERNIO_WEBHOOK_SECRET are both required for Zernio.")
        # One client per set of credentials for the life of the process.
        cached = _instances.get((api_key, webhook_secret))
        if cached is None:
            cached = _instances[(api_key, webhook_secret)] = cls(api_key, webhook_secret)
        return cached

    def _request(self, method: str, path: str, *, ok: tuple[int, ...] = (200, 201), **kwargs) -> httpx.Response:
        """One call. Network failures and 429/5xx are retryable; an expired
        account connection asks for a reconnect; anything else is permanent."""
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE, f"{type(exc).__name__}", retryable=True) from exc
        if response.status_code in ok:
            return response
        try:
            body = response.json()
        except ValueError:
            body = {}
        detail = f"{response.status_code} {body.get('code') or body.get('type') or ''}: {body.get('error') or ''}"
        if response.status_code in _RETRYABLE_HTTP:
            raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE, detail, retryable=True)
        if response.status_code == 403 and body.get("code") == "ACCOUNT_DISCONNECTED":
            raise ProviderError(ErrorCode.RECONNECT_REQUIRED, detail)
        raise ProviderError(ErrorCode.UNKNOWN, detail)

    # --- PublishingProvider -------------------------------------------------
    def create_end_user(self, user: EndUser) -> str:
        # A 409 means this user already has a profile: use it.
        response = self._request(
            "POST", "/profiles", ok=(200, 201, 409),
            json={"name": user.user_id, "externalId": user.user_id},
        )
        body = response.json()
        if response.status_code == 409:
            existing = (body.get("details") or {}).get("existingProfileId")
            if not existing:
                raise ProviderError(ErrorCode.UNKNOWN, "409 from /profiles with no existingProfileId")
            return str(existing)
        return str(body["profile"]["_id"])

    def get_connect_url(self, provider_user_ref: str, platform: Platform, redirect_url: str) -> str:
        response = self._request(
            "GET", f"/connect/{_SLUGS[platform]}",
            params={"profileId": provider_user_ref, "redirect_url": redirect_url},
        )
        return str(response.json()["authUrl"])

    def list_connected_accounts(self, provider_user_ref: str) -> list[ConnectedAccount]:
        response = self._request("GET", "/accounts", params={"profileId": provider_user_ref})
        accounts = []
        for item in response.json().get("accounts") or []:
            platform = _PLATFORMS.get(item.get("platform", ""))
            if platform is None:
                continue  # a platform Contendo does not publish to
            usable = item.get("isActive") and not item.get("needsReconnection")
            accounts.append(ConnectedAccount(
                ref=str(item["_id"]),
                platform=platform,
                display_name=item.get("displayName") or item.get("username") or "",
                status=AccountStatus.CONNECTED if usable else AccountStatus.NEEDS_RECONNECT,
            ))
        return accounts

    def disconnect_account(self, provider_user_ref: str, account_ref: str) -> None:
        self._request("DELETE", f"/accounts/{account_ref}", ok=(200, 204, 404))

    def upload_media(self, provider_user_ref: str, filename: str, content_type: str, data: bytes) -> MediaItem:
        presign = self._request(
            "POST", "/media/presign", json={"filename": filename, "contentType": content_type},
        ).json()
        try:
            uploaded = httpx.put(presign["uploadUrl"], content=data,
                                 headers={"Content-Type": content_type}, timeout=TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:
            raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE, f"{type(exc).__name__}", retryable=True) from exc
        if uploaded.status_code != 200:
            raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE, f"media upload {uploaded.status_code}", retryable=True)
        return MediaItem(ref=presign["publicUrl"], kind="video" if content_type.startswith("video/") else "image")

    def publish(
        self,
        provider_user_ref: str,
        post: PostContent,
        account_refs: list[str],
        schedule_at: datetime | None,
        *,
        idempotency_key: str,
    ) -> str:
        accounts = {account.ref: account for account in self.list_connected_accounts(provider_user_ref)}
        missing = [ref for ref in account_refs if ref not in accounts]
        if missing:
            raise ProviderError(ErrorCode.ACCOUNT_REMOVED, f"accounts not in profile: {missing}")
        body: dict[str, Any] = {
            "content": post.text,
            "platforms": [{"platform": _SLUGS[accounts[ref].platform], "accountId": ref} for ref in account_refs],
        }
        if post.media:
            body["mediaItems"] = [{"type": item.kind, "url": item.ref} for item in post.media]
        if schedule_at is None:
            body["publishNow"] = True
        else:
            body["scheduledFor"] = schedule_at.astimezone(timezone.utc).isoformat()
            body["timezone"] = "UTC"
        # 409: this content already went to that account in the last 24 hours.
        # Zernio says to treat it as success and use the existing post.
        response = self._request(
            "POST", "/posts", ok=(200, 201, 409), json=body,
            headers={"Idempotency-Key": idempotency_key},
        )
        payload = response.json()
        if response.status_code == 409:
            existing = (payload.get("details") or {}).get("existingPostId")
            if not existing:
                raise ProviderError(ErrorCode.DUPLICATE, "409 from /posts with no existingPostId")
            return str(existing)
        return str(payload["post"]["_id"])

    def get_status(self, provider_post_ref: str) -> PublishStatus:
        return _status_from_post(self._request("GET", f"/posts/{provider_post_ref}").json()["post"])

    def cancel(self, provider_post_ref: str) -> None:
        self._request("DELETE", f"/posts/{provider_post_ref}", ok=(200, 204, 404))

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> StatusUpdate | None:
        expected = hmac.new(self._webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, headers.get("x-zernio-signature", "")):
            raise PermissionError("Zernio webhook signature mismatch")
        payload = json.loads(body)
        if payload.get("event") not in _POST_EVENTS:
            return None
        post = payload.get("post") or {}
        return StatusUpdate(str(post.get("id", "")), _status_from_post(post))
