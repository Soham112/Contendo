"""Checks that the test harness itself works. If these fail, fix the setup
before trusting any other test."""

import anthropic
import httpx
import pytest

from tests.fakes.claude import UnexpectedClaudeCall


def test_app_starts_and_health_responds(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_fake_db_is_used_and_isolates_users(fake_db):
    from memory.profile_store import load_profile, save_profile

    save_profile({"name": "Alice"}, user_id="user-a")
    save_profile({"name": "Bob"}, user_id="user-b")

    assert load_profile("user-a")["name"] == "Alice"
    assert load_profile("user-b")["name"] == "Bob"
    assert len(fake_db.tables["profiles"]) == 2


def test_fake_db_starts_empty_for_each_test(fake_db):
    assert fake_db.tables.get("profiles", []) == []


def test_queued_claude_response_is_returned(claude):
    claude.queue("hello from fake claude")
    client = anthropic.Anthropic(api_key="unused")
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": "hi"}],
    )
    assert msg.content[0].text == "hello from fake claude"
    assert claude.calls[0]["model"] == "claude-sonnet-4-6"


def test_unmocked_claude_call_fails_loudly():
    client = anthropic.Anthropic(api_key="unused")
    with pytest.raises(UnexpectedClaudeCall):
        client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}],
        )


def test_network_is_blocked():
    with pytest.raises(Exception):
        httpx.get("https://example.com", timeout=2)


def test_production_auth_accepts_valid_token_and_rejects_missing(client, production, auth_headers):
    assert client.get("/profile").status_code == 401
    ok = client.get("/profile", headers=auth_headers("user-a"))
    assert ok.status_code == 200
