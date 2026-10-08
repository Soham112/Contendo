import logging
import os
import threading
import time
import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import security

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")

# The identity given to requests without a valid token when ALLOW_DEV_AUTH=1
# (local development). This is the only place the "default" user is named.
DEV_USER_ID = "default"

security_scheme = HTTPBearer(auto_error=False)

# JWKS cache: fetched at most once per TTL. On a `kid` miss we refetch once
# (Supabase key rotation), but no more than once per cooldown, so tokens with
# made-up kids can't make us hit the JWKS endpoint on every request.
_JWKS_TTL_SECONDS = 3600
_JWKS_REFETCH_COOLDOWN_SECONDS = 30
_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0
_jwks_lock = threading.Lock()


def _fetch_jwks() -> dict:
    resp = httpx.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _get_jwks(force_refresh: bool = False) -> dict:
    global _jwks_cache, _jwks_fetched_at
    with _jwks_lock:
        age = time.monotonic() - _jwks_fetched_at
        expired = _jwks_cache is None or age >= _JWKS_TTL_SECONDS
        refresh_allowed = force_refresh and age >= _JWKS_REFETCH_COOLDOWN_SECONDS
        if expired or refresh_allowed:
            _jwks_cache = _fetch_jwks()
            _jwks_fetched_at = time.monotonic()
        return _jwks_cache


def _clear_jwks_cache() -> None:
    global _jwks_cache, _jwks_fetched_at
    with _jwks_lock:
        _jwks_cache = None
        _jwks_fetched_at = 0.0


def _find_jwk(jwks: dict, kid: str | None) -> dict | None:
    for k in jwks.get("keys", []):
        if kid is None or k.get("kid") == kid:
            return k
    return None

def _reject(reason: str) -> str:
    """Handle a request that has no valid token.

    Returns the dev user when ALLOW_DEV_AUTH=1; otherwise raises a 401 whose
    body never carries the reason (it is logged here instead).
    """
    if security.current().allow_dev_auth:
        return DEV_USER_ID
    logger.warning("auth: request rejected: %s", reason)
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_user_id(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        return _reject("missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    failures: list[str] = []

    # Try HS256 with legacy JWT secret first
    if SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_exp": True}
            )
            return payload["sub"]
        except Exception as e:
            failures.append(f"HS256: {e!r}")

    # Try ES256 via Supabase JWKS
    if SUPABASE_URL:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            matching_key = _find_jwk(_get_jwks(), kid)
            if matching_key is None:
                # Unknown kid: keys may have rotated. Refetch once, then fail.
                matching_key = _find_jwk(_get_jwks(force_refresh=True), kid)

            if matching_key is None:
                raise ValueError("No matching key found in JWKS")

            # Use PyJWT's algorithm to load the key
            from jwt.algorithms import ECAlgorithm
            public_key = ECAlgorithm.from_jwk(matching_key)

            payload = jwt.decode(
                token,
                public_key,
                algorithms=["ES256"],
                audience="authenticated",
                options={"verify_exp": True}
            )
            return payload["sub"]
        except Exception as e:
            failures.append(f"ES256: {e!r}")

    return _reject("token verification failed (" + "; ".join(failures or ["no verifier configured"]) + ")")


async def get_user_id_dep(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme)
) -> str:
    auth_header = f"Bearer {credentials.credentials}" if credentials else None
    return get_user_id(auth_header)


def is_admin(user_id: str) -> bool:
    return user_id in security.current().admin_user_ids


async def require_admin(user_id: str = Depends(get_user_id_dep)) -> str:
    """The one check for admin routes: the caller's verified user ID must be in
    ADMIN_USER_IDS. Authenticated non-admins get 403."""
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user_id
