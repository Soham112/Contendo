"""Database access: the shared client is db.supabase_client.supabase."""
from typing import Iterator


def id_batches(ids: list[str], size: int = 200) -> Iterator[list[str]]:
    """Slices of ids for in_() filters, so a request URL stays short."""
    for start in range(0, len(ids), size):
        yield ids[start:start + size]
