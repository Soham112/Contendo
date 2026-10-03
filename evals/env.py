"""Import this first in every evals entry point, before any backend module.

    import env  # noqa: F401  (must be the first project import)

On import it reads evals/.env, refuses to continue unless EVAL_SUPABASE_URL is
the project named by EXPECTED_PROJECT_REF, disables dotenv.load_dotenv so
backend/.env is never read, sets every backend env var explicitly, and puts
backend/ on sys.path. See guard.py for the individual checks.
"""

import sys
from typing import Any, Mapping

import guard

try:
    CONFIG = guard.bootstrap()
except guard.EnvGuardError as _exc:
    print(f"evals env guard: {_exc}", file=sys.stderr)
    raise SystemExit(2)


def backend_client() -> Any:
    """The backend's shared Supabase client, after checking it points at the eval project."""
    from db import supabase_client
    from memory import usage_store

    for module in (supabase_client, usage_store):
        if module._SUPABASE_URL != CONFIG.supabase_url:
            raise guard.EnvGuardError(
                f"{module.__name__} was configured with {module._SUPABASE_URL!r}, "
                f"not the eval project {CONFIG.supabase_url!r}"
            )
    guard.check_dotenv_disabled()
    return supabase_client.supabase


def verify_anthropic_key() -> None:
    """Refuse unless Anthropic accepts the key. Uses token counting, which is free."""
    import anthropic
    from llm.client import HAIKU, client

    try:
        client.beta.messages.count_tokens(model=HAIKU, messages=[{"role": "user", "content": "ping"}])
    except anthropic.AuthenticationError:
        raise guard.EnvGuardError(
            "Anthropic rejected ANTHROPIC_API_KEY from evals/.env (401). Check the key is active "
            "in the console and pasted whole, without quotes."
        )
    except anthropic.PermissionDeniedError:
        raise guard.EnvGuardError("ANTHROPIC_API_KEY from evals/.env is not allowed to call the API (403)")
    except anthropic.BadRequestError as exc:
        if "credit balance" in str(exc).lower():
            raise guard.EnvGuardError(
                "the Anthropic account for ANTHROPIC_API_KEY is out of credits "
                "(Console > Plans & Billing). Nothing was run."
            )
        raise


def verify_auth_users(users: Mapping[str, str]) -> None:
    """Refuse unless every uuid is a user in the eval project's auth.users."""
    client = backend_client()
    problems = []
    for slug, uid in users.items():
        try:
            response = client.auth.admin.get_user_by_id(uid)
            if response is None or response.user is None or response.user.id != uid:
                problems.append(f"{slug} ({uid}): not found")
        except Exception as exc:  # AuthApiError for unknown ids, network errors
            problems.append(f"{slug} ({uid}): {exc}")
    if problems:
        raise guard.EnvGuardError(
            "eval users missing from auth.users in "
            f"{CONFIG.project_ref}: " + "; ".join(problems)
        )
