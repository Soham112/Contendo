import os
import re
import types
import uuid

import dotenv
import pytest

import guard
from conftest import EVAL_REF
from guard import EnvGuardError

PROD_LIKE_URL = "https://prodprojectref1234.supabase.co"


def _bootstrap(env_path, modules=None):
    environ: dict[str, str] = {}
    sys_path: list[str] = []
    config = guard.bootstrap(env_file=env_path, environ=environ, modules=modules or {}, sys_path=sys_path)
    return config, environ, sys_path


# --- URL guard --------------------------------------------------------------

@pytest.mark.parametrize("url", [
    PROD_LIKE_URL,                                       # another project
    f"http://{EVAL_REF}.supabase.co",                    # not https
    f"https://{EVAL_REF}.supabase.co.attacker.example",  # ref only as a prefix
    f"https://x{EVAL_REF}.supabase.co",                  # ref only as a suffix
    f"https://example.com/{EVAL_REF}.supabase.co",       # ref only in the path
    "",
])
def test_url_without_expected_ref_is_refused(url):
    with pytest.raises(EnvGuardError):
        guard.check_supabase_url(url, EVAL_REF)


@pytest.mark.parametrize("ref", ["", "your-eval-project-ref", "UPPERCASE123"])
def test_placeholder_or_malformed_ref_is_refused(ref):
    with pytest.raises(EnvGuardError):
        guard.check_supabase_url(f"https://{ref}.supabase.co", ref)


def test_eval_url_is_accepted():
    guard.check_supabase_url(f"https://{EVAL_REF}.supabase.co", EVAL_REF)
    guard.check_supabase_url(f"https://{EVAL_REF}.supabase.co/", EVAL_REF)


def test_bootstrap_refuses_url_without_ref_and_changes_nothing(env_file):
    original_load_dotenv = dotenv.load_dotenv
    environ: dict[str, str] = {}
    sys_path: list[str] = []
    with pytest.raises(EnvGuardError, match="refusing"):
        guard.bootstrap(env_file=env_file(EVAL_SUPABASE_URL=PROD_LIKE_URL), environ=environ, modules={}, sys_path=sys_path)
    assert environ == {}
    assert sys_path == []
    assert dotenv.load_dotenv is original_load_dotenv


# --- evals/.env contents ----------------------------------------------------

def test_missing_env_file_is_refused(tmp_path):
    with pytest.raises(EnvGuardError, match="not found"):
        _bootstrap(tmp_path / "missing.env")


def test_missing_required_key_is_refused(env_file):
    with pytest.raises(EnvGuardError, match="EVAL_SUPABASE_SERVICE_ROLE_KEY"):
        _bootstrap(env_file(EVAL_SUPABASE_SERVICE_ROLE_KEY=None))


def test_unprefixed_supabase_url_in_env_file_is_refused(env_file):
    with pytest.raises(EnvGuardError, match="unknown keys: SUPABASE_URL"):
        _bootstrap(env_file(SUPABASE_URL=PROD_LIKE_URL))


def test_bootstrap_sets_every_backend_var_explicitly(env_file):
    config, environ, sys_path = _bootstrap(env_file())
    for key in guard.BACKEND_ENV_KEYS:
        assert key in environ, key
    assert environ["SUPABASE_URL"] == f"https://{EVAL_REF}.supabase.co"
    assert environ["SUPABASE_SERVICE_ROLE_KEY"] == "test-service-role-key"
    assert environ["ENVIRONMENT"] != "production"
    assert environ["DEEPEVAL_TELEMETRY_OPT_OUT"] == "YES"
    assert sys_path == [str(guard.BACKEND_DIR)]
    assert config.project_ref == EVAL_REF


def test_bootstrap_overrides_values_already_in_the_environment(env_file):
    environ = {"SUPABASE_URL": PROD_LIKE_URL, "SUPABASE_SERVICE_ROLE_KEY": "prod-key"}
    guard.bootstrap(env_file=env_file(), environ=environ, modules={}, sys_path=[])
    assert environ["SUPABASE_URL"] == f"https://{EVAL_REF}.supabase.co"
    assert environ["SUPABASE_SERVICE_ROLE_KEY"] == "test-service-role-key"


# --- dotenv / backend/.env --------------------------------------------------

def test_refuses_when_backend_was_imported_before_env(env_file):
    fake_llm_client = types.SimpleNamespace(__file__=str(guard.BACKEND_DIR / "llm" / "client.py"))
    with pytest.raises(EnvGuardError, match="llm.client"):
        _bootstrap(env_file(), modules={"llm.client": fake_llm_client})


def test_backend_venv_packages_do_not_count_as_backend_code(env_file):
    venv_module = types.SimpleNamespace(
        __file__=str(guard.BACKEND_VENV_DIR / "lib" / "python3.11" / "site-packages" / "dotenv" / "main.py")
    )
    _bootstrap(env_file(), modules={"dotenv.main": venv_module})


def test_refuses_when_load_dotenv_is_active():
    with pytest.raises(EnvGuardError, match="load_dotenv is active"):
        guard.check_dotenv_disabled()


def test_after_bootstrap_load_dotenv_cannot_override(env_file, tmp_path, monkeypatch):
    _bootstrap(env_file())
    guard.check_dotenv_disabled()

    # A stand-in for backend/.env. The real file is never touched by tests.
    fake_backend_env = tmp_path / "backend.env"
    fake_backend_env.write_text(f"SUPABASE_URL={PROD_LIKE_URL}\nEVALS_TEST_SENTINEL=loaded\n")
    monkeypatch.delenv("EVALS_TEST_SENTINEL", raising=False)

    # Both import styles the backend uses (`from dotenv import load_dotenv`).
    from dotenv import load_dotenv
    assert load_dotenv(fake_backend_env, override=True) is False
    assert dotenv.main.load_dotenv(fake_backend_env, override=True) is False
    assert "EVALS_TEST_SENTINEL" not in os.environ


# --- drift against the backend ----------------------------------------------

_ENV_READ_RE = re.compile(r"""os\.(?:environ\.get|getenv|environ\.setdefault)\(\s*["']([A-Z0-9_]+)["']|os\.environ\[\s*["']([A-Z0-9_]+)["']\s*\]""")
_ENV_READ_BY_CONSTANT_RE = re.compile(r"""os\.(?:environ\.get|getenv|environ\.setdefault)\(\s*([A-Z_][A-Z0-9_]*)\s*[,)]""")


def test_backend_env_keys_match_backend_source():
    found: set[str] = set()
    for path in guard.BACKEND_DIR.rglob("*.py"):
        if path.is_relative_to(guard.BACKEND_VENV_DIR) or "tests" in path.relative_to(guard.BACKEND_DIR).parts:
            continue
        text = path.read_text()
        for a, b in _ENV_READ_RE.findall(text):
            found.add(a or b)
        # A variable read through a module constant (config/features.py reads
        # PIPELINE_VARIANT that way): the constant must be a string in the same file.
        for constant in _ENV_READ_BY_CONSTANT_RE.findall(text):
            named = re.findall(rf"""^{constant}\s*=\s*["']([A-Z0-9_]+)["']\s*$""", text, flags=re.MULTILINE)
            assert len(named) == 1, f"{path}: cannot tell which variable os.environ reads through {constant}"
            found.add(named[0])
    assert found == set(guard.BACKEND_ENV_KEYS), (
        "backend env vars changed; update guard.BACKEND_ENV_KEYS and build_backend_env: "
        f"missing {sorted(found - set(guard.BACKEND_ENV_KEYS))}, stale {sorted(set(guard.BACKEND_ENV_KEYS) - found)}"
    )


def test_reset_tables_match_baseline_schema():
    sql = (guard.BACKEND_DIR / "migrations" / "000_baseline_schema.sql").read_text()
    tables_with_user_id = set()
    for name, body in re.findall(r"CREATE TABLE public\.(\w+) \((.*?)\n\);", sql, re.S):
        if re.search(r"^\s+user_id\s", body, re.M):
            tables_with_user_id.add(name)
    expected = {(t, "user_id") for t in tables_with_user_id} | {("profiles", "id")}
    assert set(guard.RESET_TABLES) == expected
    assert len(guard.RESET_TABLES) == len(expected)


# --- reset targets ----------------------------------------------------------

USERS = {
    "ds": "11111111-1111-4111-8111-111111111111",
    "pm": "22222222-2222-4222-8222-222222222222",
    "founder": "33333333-3333-4333-8333-333333333333",
}


def test_reset_with_no_request_targets_every_eval_user():
    assert guard.resolve_reset_targets([], USERS) == USERS


def test_reset_accepts_slugs_and_known_uuids():
    assert guard.resolve_reset_targets(["ds"], USERS) == {"ds": USERS["ds"]}
    assert guard.resolve_reset_targets([USERS["pm"].upper()], USERS) == {"pm": USERS["pm"]}


@pytest.mark.parametrize("requested", [
    ["intern"],                      # unknown slug
    [str(uuid.uuid4())],             # a real uuid that is not an eval user
    ["ds", "default"],               # one bad item refuses the whole request
    ["' or 1=1 --"],
])
def test_reset_refuses_unknown_user_ids(requested):
    with pytest.raises(EnvGuardError, match="not an eval user"):
        guard.resolve_reset_targets(requested, USERS)


@pytest.mark.parametrize("users", [
    {"ds": "REPLACE-WITH-DS-AUTH-USER-UUID"},
    {"ds": "00000000-0000-0000-0000-000000000000"},
    {"ds": USERS["ds"], "pm": USERS["ds"]},
    {},
])
def test_reset_refuses_bad_users_file(users):
    with pytest.raises(EnvGuardError):
        guard.resolve_reset_targets([], users)


# --- Anthropic key and SDK env vars ------------------------------------------

@pytest.mark.parametrize("key, reason", [
    ("replace-with-an-anthropic-api-key", "does not start with"),
    ("sk-ant-admin01-" + "x" * 60, "Admin API key"),
    ("\u201csk-ant-api03-" + "x" * 60 + "\u201d", "does not start with"),  # curly quotes survive dotenv
    ("sk-ant-api03-" + "x" * 30 + " " + "x" * 30, "spaces or quote"),
    ("sk-ant-api03-abc", "characters"),
    ("sk-ant-api03-" + "x" * 60 + "\u200b", "U\\+200B"),  # zero-width space from a copy-paste
])
def test_unusable_anthropic_key_is_refused_without_echoing_it(env_file, key, reason):
    with pytest.raises(EnvGuardError, match=reason) as exc_info:
        _bootstrap(env_file(ANTHROPIC_API_KEY=key))
    assert key.strip('"') not in str(exc_info.value)


def test_sdk_base_url_and_auth_token_are_removed(env_file):
    from conftest import FAKE_ANTHROPIC_KEY
    environ = {"ANTHROPIC_BASE_URL": "https://proxy.example", "ANTHROPIC_AUTH_TOKEN": "other-token",
               "ANTHROPIC_API_KEY": "sk-ant-api03-shell-key"}
    guard.bootstrap(env_file=env_file(), environ=environ, modules={}, sys_path=[])
    assert "ANTHROPIC_BASE_URL" not in environ
    assert "ANTHROPIC_AUTH_TOKEN" not in environ
    assert environ["ANTHROPIC_API_KEY"] == FAKE_ANTHROPIC_KEY
