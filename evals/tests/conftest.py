"""Evals tests: no network, no backend imports, never read evals/.env or backend/.env."""

import os

# Before anything imports deepeval: it would otherwise load .env from the working
# directory and may send telemetry. (pytest.ini also disables its pytest plugin.)
os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"

import dotenv
import dotenv.main
import pytest


@pytest.fixture(autouse=True)
def restore_dotenv():
    """bootstrap() patches dotenv globally; undo it after each test."""
    original = (dotenv.load_dotenv, dotenv.main.load_dotenv)
    yield
    dotenv.load_dotenv, dotenv.main.load_dotenv = original


@pytest.fixture
def backend(monkeypatch):
    """backend/ importable for this test (its pure modules: the price table, the
    word counts), and forgotten again after it."""
    import sys

    import guard

    before = set(sys.modules)
    monkeypatch.syspath_prepend(str(guard.BACKEND_DIR))
    yield
    for name in set(sys.modules) - before:
        if name in guard.backend_modules_loaded(sys.modules):
            del sys.modules[name]


EVAL_REF = "abcdefghijklmnopqrst"
FAKE_ANTHROPIC_KEY = "sk-ant-api03-" + "x" * 60  # right shape, not a real key


@pytest.fixture
def env_file(tmp_path):
    """Write a temporary evals/.env and return a function that writes it."""
    def write(**overrides):
        values = {
            "EVAL_SUPABASE_URL": f"https://{EVAL_REF}.supabase.co",
            "EVAL_SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
            "ANTHROPIC_API_KEY": FAKE_ANTHROPIC_KEY,
            "EXPECTED_PROJECT_REF": EVAL_REF,
        }
        values.update(overrides)
        path = tmp_path / ".env"
        path.write_text("".join(f"{k}={v}\n" for k, v in values.items() if v is not None))
        return path
    return write
