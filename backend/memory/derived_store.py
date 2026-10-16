"""Delete cascade: what goes with a deleted chunk or source.

Every delete path reaches these two functions: memory.source_store.delete_sources
(Library, admin, a failed or crashed ingest) and the end of a replace
(source_store.SourceWrite.commit, which deletes the old chunk set).

Foreign keys (migration 016) remove the relational rows: deleting a chunk
removes its chunk_entities links, deleting a sources row its source_nodes row.
This module removes what no foreign key can reach:
  - entities no chunk links to any more
  - the consolidation chunk of every entity a deleted chunk was linked to: the
    brief may repeat the deleted text, so it is removed, not kept or rebuilt
  - deleted sources in topic children (a source's retrieval count goes with its
    row, by foreign key, migration 017)
  - the user's BM25 index, so keyword search stops returning deleted text
"""
from __future__ import annotations

from db import id_batches
from db.supabase_client import supabase
from memory.consolidation_store import delete_consolidation_chunks
from memory.entity_store import delete_unlinked_entities, entity_ids_for_chunks
from memory.hierarchy_store import remove_sources_from_topics
from memory.vector_store import invalidate_bm25_cache


def chunk_ids_of_sources(source_ids: list[str], user_id: str, *,
                         only_ingest: str | None = None, except_ingest: str | None = None) -> list[str]:
    """Ids of the chunks of these sources: every chunk set, or only the one one
    ingest wrote, or all but that one (chunks from before migration 016 have no
    ingest_id). A consolidation chunk's source_id is an entity id, never a source's."""
    ids: list[str] = []
    for batch in id_batches(sorted(set(source_ids))):
        rows = (supabase.table("embeddings").select("id,ingest_id").in_("source_id", batch)
                .eq("user_id", user_id).execute().data or [])
        ids += [r["id"] for r in rows
                if (only_ingest is None or r.get("ingest_id") == only_ingest)
                and (except_ingest is None or r.get("ingest_id") != except_ingest)]
    return ids


def delete_chunks(chunk_ids: list[str], user_id: str) -> int:
    """Delete these chunks and what was derived from them. Returns chunks deleted."""
    ids = sorted(set(chunk_ids))
    if not ids:
        return 0
    affected = entity_ids_for_chunks(ids, user_id)   # read before the links cascade away
    removed = 0
    for batch in id_batches(ids):
        removed += len(supabase.table("embeddings").delete().in_("id", batch)
                       .eq("user_id", user_id).execute().data or [])
    delete_unlinked_entities(affected, user_id)
    delete_consolidation_chunks(affected, user_id)
    invalidate_bm25_cache(user_id)
    return removed


def after_sources_deleted(source_ids: set[str], user_id: str) -> None:
    """Clean up after these sources' rows are deleted (their chunks already are)."""
    remove_sources_from_topics(source_ids, user_id)
