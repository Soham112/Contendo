"""No API or worker path publishes text without the user's exact approval."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from tests.test_publishing import a_headers, connect, job_row, pro, provider, tick  # noqa: F401
from memory import approval_store

CONTENT = "We sold to a young couple for $900,000."


def review(client, headers, content=CONTENT):
    response = client.post("/publishing/reviews", headers=headers, json={"content": content})
    assert response.status_code == 200
    return response.json()


def approve(client, headers, row, accepted=None):
    return client.post(f"/publishing/reviews/{row['id']}/approve", headers=headers, json={
        "content": row["content"], "accepted_flag_ids": accepted if accepted is not None else [f["id"] for f in row["flags"]]})


def body(account, **extra):
    return {"content": CONTENT, "account_ids": [account["id"]], "when": "now", **extra}


@pytest.mark.parametrize("when", ["now", "schedule", "queue"])
def test_no_publishing_or_scheduling_without_approval(client, a_headers, pro, fake_db, when):
    account = connect(client, a_headers)
    payload = body(account, when=when, scheduled_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    response = client.post("/publishing/jobs", headers=a_headers, json=payload)
    assert response.status_code == 422
    assert not fake_db.tables.get("publish_jobs")


def test_unresolved_flags_cannot_be_approved(client, a_headers, pro):
    checked = review(client, a_headers)
    assert checked["flags"]  # missing source tracking is never called clean
    assert approve(client, a_headers, checked, []).status_code == 409
    assert approve(client, a_headers, checked, ["unknown"]).status_code == 409
    assert approve(client, a_headers, checked).status_code == 200


def test_every_cached_claim_needs_its_own_acceptance(client, a_headers, pro, fake_db):
    fake_db.tables["generation_traces"] = [{
        "id": "b813726c-b834-4d4a-bdea-57808d130bb8", "user_id": "user-a", "node_outputs": {"final_post": CONTENT,
        "grounding": {"outcome": "needs_review", "flags": [
            {"id": "age", "text": "young", "reason": "age absent", "sentence": CONTENT},
            {"id": "price", "text": "$900,000", "reason": "price absent", "sentence": CONTENT}]}}}]
    checked = client.post("/publishing/reviews", headers=a_headers, json={"content": CONTENT, "trace_id": "b813726c-b834-4d4a-bdea-57808d130bb8"}).json()
    assert approve(client, a_headers, checked, ["age"]).status_code == 409
    assert approve(client, a_headers, checked, ["age", "price"]).status_code == 200


def test_editing_flagged_text_rechecks_sources_before_approval(client, a_headers, pro, fake_db, claude):
    fake_db.tables["generation_traces"] = [{"id": "b813726c-b834-4d4a-bdea-57808d130bb8", "user_id": "user-a", "topic": "Just sold",
        "retrieved": [{"text": "We sold the home to a couple.", "source_type": "personal_note", "memory_context": "work"}],
        "node_outputs": {"final_post": CONTENT}}]
    claude.queue(json.dumps({"sentences": [{"sentence": 1, "unsupported": []}]}))
    corrected = "We sold the home to a couple."
    checked = client.post("/publishing/reviews", headers=a_headers, json={"content": corrected, "trace_id": "b813726c-b834-4d4a-bdea-57808d130bb8"}).json()
    assert checked["flags"] == []
    assert approve(client, a_headers, checked, []).status_code == 200
    assert len(claude.calls) == 1


def test_text_or_media_changes_invalidate_approval(client, a_headers, pro, provider):
    account = connect(client, a_headers)
    checked = review(client, a_headers)
    assert approve(client, a_headers, checked).status_code == 200
    for changes in [{"content": "Different text."}, {"media": [{"ref": "new", "kind": "image"}]}]:
        response = client.post("/publishing/jobs", headers=a_headers, json=body(account, approval_id=checked["id"], **changes))
        assert response.status_code == 422
    assert provider.publish_calls == []


def test_approval_is_user_scoped(client, a_headers, auth_headers, pro):
    checked = review(client, a_headers)
    pro("user-b")
    assert approve(client, auth_headers("user-b"), checked).status_code == 409
    assert approval_store.get_review("user-b", checked["id"]) is None


def test_worker_checks_approved_snapshot_again(client, a_headers, pro, fake_db, provider):
    account = connect(client, a_headers)
    checked = review(client, a_headers)
    assert approve(client, a_headers, checked).status_code == 200
    assert client.post("/publishing/jobs", headers=a_headers, json=body(account, approval_id=checked["id"])).status_code == 200
    job_row(fake_db)["content"] = "Unapproved changed text."
    tick()
    assert job_row(fake_db)["error_code"] == "approval_required"
    assert provider.publish_calls == []


def test_legacy_jobs_without_approval_never_publish(client, a_headers, pro, fake_db, provider):
    from memory import publish_store
    account = connect(client, a_headers)
    publish_store.create_job("user-a", provider="fake", content=CONTENT, account_ids=[account["id"]],
                             post_id=None, scheduled_at=None)
    tick()
    assert job_row(fake_db)["error_code"] == "approval_required"
    assert provider.publish_calls == []


def test_auto_publish_option_is_not_accepted(client, a_headers, pro):
    account = connect(client, a_headers)
    response = client.post("/publishing/jobs", headers=a_headers, json=body(account, auto_publish=True))
    assert response.status_code == 422


def test_approval_is_idempotent_and_content_changes_require_new_review(client, a_headers, pro):
    checked = review(client, a_headers)
    first = approve(client, a_headers, checked)
    second = approve(client, a_headers, checked)
    assert first.status_code == second.status_code == 200
    assert first.json()["approved_at"] == second.json()["approved_at"]
    changed = client.post(f"/publishing/reviews/{checked['id']}/approve", headers=a_headers,
                         json={"content": "Changed text.", "accepted_flag_ids": []})
    assert changed.status_code == 409


def test_malformed_approval_id_is_rejected_before_database_access(client, a_headers, pro):
    account = connect(client, a_headers)
    assert client.post("/publishing/jobs", headers=a_headers, json=body(account, approval_id="not-a-uuid")).status_code == 422
