"""Provider synchronization must not bypass per-platform entitlements."""
import pytest
from memory import publish_store
from publishing.types import AccountStatus, ConnectedAccount, Platform


def test_provider_duplicates_are_rejected_before_any_accounts_are_written(fake_db):
    with pytest.raises(publish_store.AccountLimitError):
        publish_store.sync_accounts("user-a", "fake", [
            ConnectedAccount("one", Platform.LINKEDIN, "One"),
            ConnectedAccount("two", Platform.LINKEDIN, "Two"),
        ])
    assert not fake_db.tables.get("connected_accounts")


@pytest.mark.parametrize("include_disconnected", [False, True])
def test_sync_releases_the_old_slot_before_inserting_a_replacement(fake_db, monkeypatch, include_disconnected):
    from tests.fakes.supabase import FakeQuery
    fake_db.tables["connected_accounts"] = [{
        "id": "old-id", "user_id": "user-a", "provider": "fake", "provider_account_ref": "old-ref",
        "platform": "linkedin", "display_name": "Old", "status": "needs_reconnect", "created_at": "2026-10-13",
    }]
    original = FakeQuery.upsert
    def require_slot_free(query, row, **kwargs):
        if query._table == "connected_accounts" and row["provider_account_ref"] == "new-ref":
            # Model the real partial unique index at the point the INSERT runs.
            assert fake_db.tables["connected_accounts"][0]["status"] == "disconnected"
        return original(query, row, **kwargs)
    monkeypatch.setattr(FakeQuery, "upsert", require_slot_free)
    current = [ConnectedAccount("new-ref", Platform.LINKEDIN, "New")]
    if include_disconnected:
        current.append(ConnectedAccount("old-ref", Platform.LINKEDIN, "Old", AccountStatus.DISCONNECTED))
    result = publish_store.sync_accounts("user-a", "fake", current)
    assert len(result) == 1 and result[0]["provider_account_ref"] == "new-ref"
