"""Safety checks for evals. Pure functions: importing this module changes nothing.

env.py calls bootstrap() to point the backend at the eval Supabase project.
Everything here raises EnvGuardError instead of guessing, so a misconfigured
run stops before it reads or writes any data.
"""

import os
import re
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, MutableSequence
from urllib.parse import urlparse

import dotenv
import dotenv.main

EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
BACKEND_VENV_DIR = BACKEND_DIR / "venv"
DEFAULT_ENV_FILE = EVALS_DIR / ".env"
USERS_FILE = EVALS_DIR / "fixtures" / "users.json"

# Keys evals/.env must set.
REQUIRED_FILE_KEYS = (
    "EVAL_SUPABASE_URL",
    "EVAL_SUPABASE_SERVICE_ROLE_KEY",
    "ANTHROPIC_API_KEY",
    "EXPECTED_PROJECT_REF",
)
# Keys evals/.env may set to override a safe default.
OPTIONAL_FILE_KEYS = ("LOG_LEVEL", "SUPABASE_JWT_SECRET")

# Every environment variable the backend reads (tests/test_guard.py checks this
# list against the backend source). Each one is set explicitly by bootstrap().
BACKEND_ENV_KEYS = (
    "ADMIN_SECRET",
    "ANTHROPIC_API_KEY",
    "DATA_DIR",
    "ENVIRONMENT",
    "FRONTEND_ORIGIN",
    "LOG_LEVEL",
    "SUPABASE_JWT_SECRET",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_URL",
    "SUPADATA_API_KEY",
    "TAVILY_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)

# Read by the Anthropic SDK itself, not the backend. Removed so requests go to
# api.anthropic.com with the key from evals/.env and nothing else.
SDK_ENV_REMOVED = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN")

# DeepEval settings: no telemetry, and never let it auto-load a .env file.
DEEPEVAL_ENV = {
    "DEEPEVAL_TELEMETRY_OPT_OUT": "YES",
    "DEEPEVAL_DISABLE_DOTENV": "1",
}

# Tables in backend/migrations/000_baseline_schema.sql that hold per-user rows,
# with the column that holds the user id. Ordered for deletion: traces before
# posts, links before entities. tests/test_guard.py checks this against the schema.
RESET_TABLES: tuple[tuple[str, str], ...] = (
    ("generation_traces", "user_id"),
    ("posts", "user_id"),  # post_versions cascade on delete
    ("chunk_entities", "user_id"),
    ("entities", "user_id"),
    ("embeddings", "user_id"),
    ("source_nodes", "user_id"),
    ("topic_nodes", "user_id"),
    ("source_retrieval_stats", "user_id"),
    ("experience_nodes", "user_id"),
    ("usage_events", "user_id"),
    ("user_events", "user_id"),
    ("profiles", "id"),
)

_PROJECT_REF_RE = re.compile(r"^[a-z0-9]{8,40}$")


class EnvGuardError(RuntimeError):
    """A safety check failed. The run must stop."""


@dataclass(frozen=True)
class EvalConfig:
    supabase_url: str
    project_ref: str
    data_dir: str


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_supabase_url(url: str, expected_ref: str) -> None:
    """Refuse unless url is https://<expected_ref>.supabase.co."""
    if not expected_ref or not _PROJECT_REF_RE.match(expected_ref):
        raise EnvGuardError(
            f"EXPECTED_PROJECT_REF must be the eval project's ref (lowercase letters "
            f"and digits), got {expected_ref!r}"
        )
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host != f"{expected_ref}.supabase.co":
        raise EnvGuardError(
            f"EVAL_SUPABASE_URL host {host or '(none)'!r} is not "
            f"{expected_ref}.supabase.co: refusing to run against another project"
        )


def check_anthropic_key(key: str) -> None:
    """Refuse keys that cannot work. Messages describe the problem, never the key."""
    if not key.startswith("sk-ant-"):
        raise EnvGuardError("ANTHROPIC_API_KEY in evals/.env does not start with 'sk-ant-' (placeholder or wrong value?)")
    if key.startswith("sk-ant-admin"):
        raise EnvGuardError("ANTHROPIC_API_KEY in evals/.env is an Admin API key; it cannot call the Messages API")
    if any(c.isspace() or c in "\"'`" for c in key):
        raise EnvGuardError("ANTHROPIC_API_KEY in evals/.env contains spaces or quote characters (paste error?)")
    bad = sorted({f"U+{ord(c):04X}" for c in key if not (c.isascii() and (c.isalnum() or c in "-_"))})
    if bad:
        raise EnvGuardError(
            f"ANTHROPIC_API_KEY in evals/.env contains characters a key never has: {', '.join(bad)} "
            "(often an invisible character from a copy-paste)"
        )
    if len(key) < 40:
        raise EnvGuardError(f"ANTHROPIC_API_KEY in evals/.env is only {len(key)} characters (truncated paste?)")


def read_env_file(path: Path) -> dict[str, str]:
    """Read evals/.env without touching os.environ and without searching for other files."""
    if not path.is_file():
        raise EnvGuardError(f"{path} not found: copy evals/.env.example to evals/.env and fill it in")
    values = dotenv.dotenv_values(path, interpolate=False)
    return {k: (v or "").strip() for k, v in values.items()}


def check_env_file_keys(values: Mapping[str, str]) -> None:
    """Refuse missing required keys and unknown keys (unprefixed SUPABASE_URL, typos)."""
    missing = [k for k in REQUIRED_FILE_KEYS if not values.get(k)]
    if missing:
        raise EnvGuardError(f"evals/.env is missing: {', '.join(missing)}")
    unknown = sorted(set(values) - set(REQUIRED_FILE_KEYS) - set(OPTIONAL_FILE_KEYS))
    if unknown:
        raise EnvGuardError(
            f"evals/.env has unknown keys: {', '.join(unknown)} "
            f"(allowed: {', '.join(REQUIRED_FILE_KEYS + OPTIONAL_FILE_KEYS)})"
        )


def build_backend_env(values: Mapping[str, str], data_dir: str) -> dict[str, str]:
    """Every backend env var, set explicitly. Nothing is left for a .env file to fill."""
    env = {
        "SUPABASE_URL": values["EVAL_SUPABASE_URL"],
        "SUPABASE_SERVICE_ROLE_KEY": values["EVAL_SUPABASE_SERVICE_ROLE_KEY"],
        "ANTHROPIC_API_KEY": values["ANTHROPIC_API_KEY"],
        "SUPABASE_JWT_SECRET": values.get("SUPABASE_JWT_SECRET") or "evals-dummy-jwt-secret-not-used-by-the-pipeline",
        "ENVIRONMENT": "eval",
        "ADMIN_SECRET": "evals-dummy-admin-secret",
        "DATA_DIR": data_dir,
        "LOG_LEVEL": values.get("LOG_LEVEL") or "WARNING",
        "FRONTEND_ORIGIN": "",
        "SUPADATA_API_KEY": "",
        "TAVILY_API_KEY": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
    }
    assert set(env) == set(BACKEND_ENV_KEYS), "build_backend_env out of sync with BACKEND_ENV_KEYS"
    return {**env, **DEEPEVAL_ENV}


def backend_modules_loaded(modules: Mapping[str, Any]) -> list[str]:
    """Names of already-imported modules whose file lives in backend/ (venv excluded)."""
    loaded = []
    for name, module in list(modules.items()):
        file = getattr(module, "__file__", None)
        if not file:
            continue
        path = Path(file).resolve()
        if path.is_relative_to(BACKEND_DIR) and not path.is_relative_to(BACKEND_VENV_DIR):
            loaded.append(name)
    return sorted(loaded)


def check_backend_not_imported(modules: Mapping[str, Any]) -> None:
    """Refuse if backend code ran before env.py: its load_dotenv() may have read backend/.env."""
    loaded = backend_modules_loaded(modules)
    if loaded:
        raise EnvGuardError(
            "backend modules were imported before evals/env.py, so backend/.env may "
            f"already be loaded: {', '.join(loaded)}. Import env first."
        )


def _load_dotenv_disabled(*args: Any, **kwargs: Any) -> bool:
    """Replacement for dotenv.load_dotenv: loads nothing."""
    return False


def disable_dotenv() -> None:
    """Make every later load_dotenv() call (llm/client.py, main.py) a no-op."""
    dotenv.load_dotenv = _load_dotenv_disabled
    dotenv.main.load_dotenv = _load_dotenv_disabled


def check_dotenv_disabled() -> None:
    """Refuse if a load_dotenv() call could still read backend/.env."""
    if dotenv.load_dotenv is not _load_dotenv_disabled or dotenv.main.load_dotenv is not _load_dotenv_disabled:
        raise EnvGuardError("dotenv.load_dotenv is active: backend/.env could override the eval settings")


def check_environ(environ: Mapping[str, str], expected: Mapping[str, str]) -> None:
    wrong = [k for k, v in expected.items() if environ.get(k) != v]
    if wrong:
        raise EnvGuardError(f"environment variables not applied: {', '.join(wrong)}")


# ---------------------------------------------------------------------------
# Users and reset targets
# ---------------------------------------------------------------------------

def parse_user_id(value: str) -> str:
    """Canonical uuid string, or EnvGuardError (placeholders and the nil uuid included)."""
    try:
        parsed = uuid.UUID(str(value))
    except ValueError:
        raise EnvGuardError(f"{value!r} is not a uuid: put the auth user's id in evals/fixtures/users.json")
    if parsed.int == 0:
        raise EnvGuardError("the nil uuid is not a real auth user")
    return str(parsed)


def validate_users(users: Mapping[str, str]) -> dict[str, str]:
    """users.json content (slug -> uuid) validated: real uuids, no duplicates."""
    if not users:
        raise EnvGuardError("users.json is empty")
    parsed = {slug: parse_user_id(uid) for slug, uid in users.items()}
    if len(set(parsed.values())) != len(parsed):
        raise EnvGuardError("users.json maps two personas to the same uuid")
    return parsed


def resolve_reset_targets(requested: Iterable[str], users: Mapping[str, str]) -> dict[str, str]:
    """Map requested persona slugs or uuids to {slug: uuid}. Refuses anything not in users.json.

    An empty request means every eval user.
    """
    users = validate_users(users)
    by_uuid = {uid: slug for slug, uid in users.items()}
    requested = list(requested)
    if not requested:
        return dict(users)
    targets: dict[str, str] = {}
    for item in requested:
        if item in users:
            targets[item] = users[item]
            continue
        try:
            uid = str(uuid.UUID(item))
        except ValueError:
            uid = None
        if uid is not None and uid in by_uuid:
            targets[by_uuid[uid]] = uid
            continue
        raise EnvGuardError(f"{item!r} is not an eval user in users.json: refusing to delete its rows")
    return targets


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def bootstrap(
    env_file: Path = DEFAULT_ENV_FILE,
    environ: MutableMapping[str, str] = os.environ,
    modules: Mapping[str, Any] = sys.modules,
    sys_path: MutableSequence[str] = sys.path,
) -> EvalConfig:
    """Point the backend at the eval project. Raises EnvGuardError on any doubt."""
    check_backend_not_imported(modules)
    values = read_env_file(env_file)
    check_env_file_keys(values)
    check_supabase_url(values["EVAL_SUPABASE_URL"], values["EXPECTED_PROJECT_REF"])
    check_anthropic_key(values["ANTHROPIC_API_KEY"])

    data_dir = tempfile.mkdtemp(prefix="contendo-evals-data-")
    backend_env = build_backend_env(values, data_dir)

    disable_dotenv()
    environ.update(backend_env)
    for key in SDK_ENV_REMOVED:
        environ.pop(key, None)
    check_dotenv_disabled()
    check_environ(environ, backend_env)
    if any(key in environ for key in SDK_ENV_REMOVED):
        raise EnvGuardError(f"could not clear {', '.join(SDK_ENV_REMOVED)} from the environment")

    backend = str(BACKEND_DIR)
    if backend not in sys_path:
        sys_path.insert(0, backend)

    return EvalConfig(
        supabase_url=backend_env["SUPABASE_URL"],
        project_ref=values["EXPECTED_PROJECT_REF"],
        data_dir=data_dir,
    )
