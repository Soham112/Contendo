"""Provider synchronization must not bypass per-platform entitlements."""
import pytest
from memory import publish_store
from publishing.types import ConnectedAccount, Platform


def test_provider_duplicates_are_rejected_before_any_accounts_are_written(fake_db):
    with pytest.raises(publish_store.AccountLimitError):
        publish_store.sync_accounts("user-a", "fake", [
            ConnectedAccount("one", Platform.LINKEDIN, "One"),
            ConnectedAccount("two", Platform.LINKEDIN, "Two"),
        ])
    assert not fake_db.tables.get("connected_accounts")
