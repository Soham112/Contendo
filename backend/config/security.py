"""Security settings read from the environment.

Everything here fails closed: a flag is on only when its variable is exactly
"1", and a missing ENVIRONMENT is never treated as development.

- ENVIRONMENT              "production" on Railway. Only used to refuse unsafe
                           combinations; it never relaxes a check.
- ALLOW_DEV_AUTH           "1" lets a request with a missing or invalid token
                           act as the local dev user. Local development only.
- ALLOW_LOCAL_PATH_INGEST  "1" enables the Obsidian routes that read a folder
                           on the server's disk. Local development only.
- ADMIN_USER_IDS           comma-separated Supabase user IDs (the JWT "sub")
                           allowed to call admin routes. Empty: nobody is admin.
"""

import os
from dataclasses import dataclass


class SecurityConfigError(RuntimeError):
    """The environment asks for a combination that must never run."""


@dataclass(frozen=True)
class SecuritySettings:
    environment: str
    allow_dev_auth: bool
    allow_local_path_ingest: bool
    admin_user_ids: frozenset[str]


def current() -> SecuritySettings:
    """Settings for the current environment.

    Read on every call (four env lookups), so there is no cached copy that can
    disagree with the environment. Raises SecurityConfigError on an unsafe
    combination; main.py calls this at startup, so the server refuses to start.
    """
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    allow_dev_auth = os.environ.get("ALLOW_DEV_AUTH", "").strip() == "1"
    if allow_dev_auth and environment == "production":
        raise SecurityConfigError(
            "ALLOW_DEV_AUTH=1 cannot be combined with ENVIRONMENT=production: "
            "it would let unauthenticated requests through. Remove ALLOW_DEV_AUTH."
        )
    admin_ids = os.environ.get("ADMIN_USER_IDS", "").split(",")
    return SecuritySettings(
        environment=environment,
        allow_dev_auth=allow_dev_auth,
        allow_local_path_ingest=os.environ.get("ALLOW_LOCAL_PATH_INGEST", "").strip() == "1",
        admin_user_ids=frozenset(part.strip() for part in admin_ids if part.strip()),
    )
