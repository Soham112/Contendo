"""Shared test setup for the Contendo backend.

Everything above the fixtures runs BEFORE any backend module is imported, so the
app is wired to fakes from the start:

- Supabase      -> tests/fakes/supabase.py (in-memory tables, reset per test)
- Claude        -> tests/fakes/claude.py   (queued responses; unmocked calls fail)
- Embeddings    -> tests/fakes/embedder.py (no model download)
- Network       -> outbound connections are blocked
- Environment   -> fixed test values, so backend/.env is never used

No test can reach production data or spend API credits.
"""

import json
import os
import socket
import sys
import tempfile
import time
import types

# --- 1. Environment: set every variable the backend reads. load_dotenv() never
#        overrides a variable that already exists, so backend/.env is ignored.
TEST_JWT_SECRET = "test-jwt-secret-that-is-at-least-32-bytes-long"
TEST_ADMIN_USER_ID = "admin-user"
os.environ.update({
    "ENVIRONMENT": "development",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "SUPABASE_URL": "",
    "SUPABASE_SERVICE_ROLE_KEY": "",
    "SUPABASE_JWT_SECRET": TEST_JWT_SECRET,
    "ADMIN_USER_IDS": f"{TEST_ADMIN_USER_ID}, another-admin",
    # Set (to off) so a developer's backend/.env can't switch them on for tests.
    "ALLOW_DEV_AUTH": "",
    "ALLOW_LOCAL_PATH_INGEST": "",
    "SUPADATA_API_KEY": "",
    "FRONTEND_ORIGIN": "",
    "DATA_DIR": tempfile.mkdtemp(prefix="contendo-test-data-"),
})

# --- 2. Fakes installed in place of real modules.
from tests.fakes.claude import FakeClaude  # noqa: E402
from tests.fakes.embedder import FakeSentenceTransformer  # noqa: E402
from tests.fakes.supabase import FakeSupabase  # noqa: E402

_fake_db = FakeSupabase()
_fake_claude = FakeClaude()

_db_module = types.ModuleType("db.supabase_client")
_db_module.supabase = _fake_db
sys.modules["db.supabase_client"] = _db_module

_st_module = types.ModuleType("sentence_transformers")
_st_module.SentenceTransformer = FakeSentenceTransformer
sys.modules["sentence_transformers"] = _st_module

import anthropic.resources.messages as _anthropic_messages  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402


# --- Fixtures --------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_each_test(monkeypatch):
    """Fresh fakes per test, Claude patched, network blocked."""
    _fake_db.reset()
    _fake_claude.reset()

    vector_store = sys.modules.get("memory.vector_store")
    if vector_store is not None:
        vector_store._bm25_cache.clear()

    def _create(self, **kwargs):
        return _fake_claude.create(**kwargs)

    async def _acreate(self, **kwargs):
        return _fake_claude.create(**kwargs)

    monkeypatch.setattr(_anthropic_messages.Messages, "create", _create)
    monkeypatch.setattr(_anthropic_messages.AsyncMessages, "create", _acreate)

    real_connect = socket.socket.connect

    def _guarded_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError(f"Network access is blocked in tests (tried {address!r})")
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    yield


@pytest.fixture
def fake_db() -> FakeSupabase:
    """The in-memory Supabase. Seed or inspect via fake_db.tables["<name>"]."""
    return _fake_db


@pytest.fixture
def claude() -> FakeClaude:
    """The fake Claude API. Queue responses with claude.queue("...")."""
    return _fake_claude


@pytest.fixture
def client():
    """FastAPI TestClient for the real app (runs lifespan startup)."""
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as c:
        yield c


# Replies for the structured calls (see tests/fakes/claude.py): queue these as-is.
ARCHETYPE_GENERAL = '{"archetype": "general"}'
_ALL_STRONG = {area: {"verdict": "strong", "fix": None} for area in ("topic", "hook", "substance", "structure", "voice")}
CRITIC_ALL_STRONG = json.dumps({**_ALL_STRONG, "overall": "postable"})


def score_json(per_dimension: int = 16) -> str:
    """A valid scorer reply whose total is 5 * per_dimension."""
    dims = ("natural_voice", "sentence_variety", "precision", "no_llm_fingerprints", "value_delivery")
    return json.dumps({"dimension_scores": {d: per_dimension for d in dims}, "flagged_sentences": [], "feedback": []})


def make_token(user_id: str, *, expires_in: int = 3600, secret: str = TEST_JWT_SECRET) -> str:
    """A Supabase-style HS256 access token for user_id."""
    now = int(time.time())
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated", "iat": now, "exp": now + expires_in},
        secret,
        algorithm="HS256",
    )


@pytest.fixture
def auth_headers():
    """auth_headers("user-a") -> {"Authorization": "Bearer <token for user-a>"}."""
    def _headers(user_id: str, **kwargs) -> dict:
        return {"Authorization": f"Bearer {make_token(user_id, **kwargs)}"}
    return _headers


@pytest.fixture
def production(monkeypatch):
    """Run the test with ENVIRONMENT=production. Auth is strict in every
    environment; this only proves production behaves the same."""
    monkeypatch.setenv("ENVIRONMENT", "production")


@pytest.fixture
def dev_auth(monkeypatch):
    """ALLOW_DEV_AUTH=1: requests without a valid token act as the dev user."""
    monkeypatch.setenv("ALLOW_DEV_AUTH", "1")


@pytest.fixture
def no_specifics_on(monkeypatch):
    """Force NO_SPECIFICS_MODE_ENABLED on: the mode is disabled by default, but its
    code paths stay tested."""
    from config import features

    monkeypatch.setattr(features, "NO_SPECIFICS_MODE_ENABLED", True)
