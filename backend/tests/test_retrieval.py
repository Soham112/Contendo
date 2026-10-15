"""Retrieval helpers: confidence classification, RRF fusion, and the retrieval node."""

import pytest


def _hits(*similarities, bm25=()):
    hits = [{"id": f"c{i}", "similarity": s} for i, s in enumerate(similarities)]
    hits += [{"id": f"b{i}", "similarity": 0.0, "bm25_norm": b} for i, b in enumerate(bm25)]
    return hits


# --- Confidence --------------------------------------------------------------
# From top-1 real cosine and top-1 normalized BM25 (config/retrieval.py):
# high: cosine >= 0.45; medium: cosine >= 0.30 or BM25 >= 0.30; else low.

@pytest.mark.parametrize("similarities, bm25, expected", [
    ((), (), "low"),
    ((0.1, 0.2), (), "low"),
    ((0.29, 0.29, 0.29), (0.29,), "low"),   # many near-misses still don't count
    ((0.30,), (), "medium"),
    ((0.1,), (0.30,), "medium"),            # a strong keyword match alone
    ((0.44,), (0.9,), "medium"),            # BM25 never makes it "high"
    ((0.45,), (), "high"),
    ((0.1, 0.7), (), "high"),               # only the best hit matters
])
def test_retrieval_confidence_thresholds(similarities, bm25, expected):
    from agents.retrieval_agent import _compute_retrieval_confidence

    assert _compute_retrieval_confidence(_hits(*similarities, bm25=bm25)) == expected


# --- RRF fusion ----------------------------------------------------------------

def test_rrf_ranks_chunks_found_by_both_searches_first():
    from memory.vector_store import _rrf_merge

    vector = [{"id": "only-vector", "similarity": 0.9}, {"id": "both", "similarity": 0.5}]
    bm25 = [{"id": "only-bm25", "similarity": 0.35}, {"id": "both", "similarity": 0.35}]

    merged = _rrf_merge(vector, bm25, n_results=3)
    assert merged[0]["id"] == "both"


def test_rrf_keeps_real_vector_similarity_for_shared_chunks():
    from memory.vector_store import _rrf_merge

    vector = [{"id": "both", "similarity": 0.72}]
    bm25 = [{"id": "both", "similarity": 0.35}]

    assert _rrf_merge(vector, bm25)[0]["similarity"] == 0.72


def test_rrf_respects_result_limit():
    from memory.vector_store import _rrf_merge

    vector = [{"id": f"v{i}", "similarity": 0.5} for i in range(10)]
    bm25 = [{"id": f"b{i}", "similarity": 0.35} for i in range(10)]

    assert len(_rrf_merge(vector, bm25, n_results=8)) == 8


def test_keyword_only_matches_do_not_inflate_confidence():
    from agents.retrieval_agent import _compute_retrieval_confidence
    from memory.vector_store import _rrf_merge

    vector = [{"id": f"v{i}", "similarity": 0.05} for i in range(3)]          # semantically unrelated
    bm25 = [{"id": f"b{i}", "bm25_score": 1.2, "bm25_norm": 0.07} for i in range(3)]  # weak keyword hits

    assert _compute_retrieval_confidence(_rrf_merge(vector, bm25)) == "low"


# --- Retrieval node ------------------------------------------------------------

def test_retrieval_node_uses_only_the_requesting_users_chunks():
    from agents.retrieval_agent import retrieval_node
    from memory.vector_store import upsert_chunks

    upsert_chunks(["pgvector makes retrieval fast"], source_title="A notes", user_id="user-a")
    upsert_chunks(["pgvector index tuning for retrieval"], source_title="B notes", user_id="user-b")

    state = retrieval_node({"topic": "pgvector retrieval", "user_id": "user-b"})

    assert state["retrieved_chunk_count"] >= 1
    assert all("tuning" in c for c in state["retrieved_chunks"])


def test_retrieval_node_with_empty_knowledge_base_reports_low_confidence():
    from agents.retrieval_agent import retrieval_node

    state = retrieval_node({"topic": "anything", "user_id": "new-user"})

    assert state["retrieved_chunks"] == []
    assert state["retrieval_confidence"] == "low"


# --- Source context: one query per table ----------------------------------------

def _seed_chunk(fake_db, user, sid, idx, text, source_type="note"):
    fake_db.tables.setdefault("embeddings", []).append({
        "id": f"{sid}_{idx}", "user_id": user, "source_id": sid, "chunk_index": idx,
        "content": text, "source_type": source_type,
    })


def _selects(fake_db, table):
    return sum(1 for t, op in fake_db.log if (t, op) == (table, "select"))


def test_source_context_is_built_with_one_query_per_table(fake_db):
    from agents.retrieval_agent import _build_retrieval_bundle

    for idx in range(8):
        _seed_chunk(fake_db, "u", "src-a", idx, f"a{idx}")
        _seed_chunk(fake_db, "u", "src-b", idx, f"b{idx}")
    _seed_chunk(fake_db, "u", "src-c", 0, "c0")
    _seed_chunk(fake_db, "u", "src-c", 1, "c1")
    _seed_chunk(fake_db, "u", "src-d", 1, "d1")
    _seed_chunk(fake_db, "other", "src-a", 2, "other user's a2")
    fake_db.tables["source_nodes"] = [
        {"user_id": "u", "source_id": "src-a", "source_title": "A", "source_type": "note",
         "source_summary": "about a", "topic_id": "t1", "tags": "x,y"},
        {"user_id": "u", "source_id": "src-b", "source_title": "B", "source_type": "article",
         "source_summary": "about b", "topic_id": "t1", "tags": ""},
        {"user_id": "u", "source_id": "src-d", "source_title": "D", "source_type": "note",
         "source_summary": "about d", "topic_id": "t2", "tags": ""},
        {"user_id": "other", "source_id": "src-c", "source_title": "not yours", "topic_id": "t9"},
    ]
    fake_db.tables["topic_nodes"] = [
        {"user_id": "u", "topic_id": "t1", "topic_label": "T1", "topic_summary": "s1"},
        {"user_id": "u", "topic_id": "t2", "topic_label": "T2", "topic_summary": "s2"},
        {"user_id": "other", "topic_id": "t9", "topic_label": "not yours"},
    ]
    fake_db.log.clear()

    chunks = [
        {"source_id": "src-a", "chunk_index": 1, "source_type": "note"},
        {"source_id": "src-b", "chunk_index": 6, "source_type": "article"},
        {"source_id": "src-a", "chunk_index": 5},                      # later match, same source
        {"source_id": "src-c", "chunk_index": 0, "source_type": "pdf"},  # no node for this user
        {"source_id": "src-d", "chunk_index": 1},                      # 4th source: no siblings
    ]
    bundle = _build_retrieval_bundle(chunks, "u")

    ctx = bundle["source_contexts"]
    assert list(ctx) == ["src-a", "src-b", "src-c", "src-d"]
    # Siblings sit in each source's own window around its first match, nothing else
    assert ctx["src-a"]["sibling_chunks"] == ["a0", "a2"]
    assert ctx["src-b"]["sibling_chunks"] == ["b5", "b7"]
    assert ctx["src-c"]["sibling_chunks"] == ["c1"]
    assert ctx["src-d"]["sibling_chunks"] == []
    assert ctx["src-a"]["source_summary"] == "about a"
    # Pre-migration (or another user's) source falls back to chunk metadata
    assert ctx["src-c"] == {"source_title": "", "source_type": "pdf",
                            "source_summary": "", "sibling_chunks": ["c1"]}
    # Topics once each, in order of the first source naming them
    assert bundle["topic_contexts"] == [{"topic_label": "T1", "topic_summary": "s1"},
                                        {"topic_label": "T2", "topic_summary": "s2"}]
    assert (_selects(fake_db, "source_nodes"), _selects(fake_db, "topic_nodes"),
            _selects(fake_db, "embeddings")) == (1, 1, 1)


def test_source_context_with_no_chunks_makes_no_sibling_or_topic_query(fake_db):
    from agents.retrieval_agent import _build_retrieval_bundle

    fake_db.log.clear()
    bundle = _build_retrieval_bundle([], "u")

    assert bundle == {"chunks": [], "source_contexts": {}, "topic_contexts": []}
    assert fake_db.log == []


def test_a_failed_source_lookup_still_returns_chunk_metadata(fake_db, monkeypatch):
    import agents.retrieval_agent as ra

    def boom(*_, **__):
        raise RuntimeError("db down")

    monkeypatch.setattr(ra, "get_source_nodes", boom)
    bundle = ra._build_retrieval_bundle([{"source_id": "s", "chunk_index": 0, "source_type": "note"}], "u")

    assert bundle["source_contexts"]["s"]["source_type"] == "note"
    assert bundle["topic_contexts"] == []


# --- Retrieval stats ---------------------------------------------------------------

def test_record_retrievals_counts_each_distinct_title_once_per_user(fake_db):
    from memory.retrieval_stats_store import get_retrieval_counts, record_retrievals

    fake_db.tables["source_retrieval_stats"] = [
        {"id": 1, "user_id": "u", "source_title": "Old", "retrieval_count": 4},
        {"id": 2, "user_id": "other", "source_title": "New", "retrieval_count": 9},
    ]
    record_retrievals("u", ["Old", "New", " New ", "", "Old"])

    assert get_retrieval_counts("u") == {"Old": 5, "New": 1}
    assert get_retrieval_counts("other") == {"New": 9}


def test_record_retrievals_with_no_titles_touches_nothing(fake_db):
    from memory.retrieval_stats_store import record_retrievals

    record_retrievals("u", ["", "  "])
    assert fake_db.log == []


def test_retrieval_does_not_wait_for_stats_writes(fake_db, monkeypatch):
    import threading

    import memory.retrieval_stats_store as stats
    from agents.retrieval_agent import retrieval_node
    from memory.vector_store import upsert_chunks

    upsert_chunks(["pgvector makes retrieval fast"], source_title="Notes", user_id="u")
    release, started = threading.Event(), threading.Event()
    real = stats.record_retrievals

    def slow_write(*args):
        started.set()
        release.wait(5)
        real(*args)

    monkeypatch.setattr(stats, "record_retrievals", slow_write)
    state = retrieval_node({"topic": "pgvector retrieval", "user_id": "u"})

    assert state["retrieved_chunk_count"] == 1          # returned while the write is blocked
    assert started.wait(5) and stats.get_retrieval_counts("u") == {}
    release.set()
    stats.flush_pending_retrievals()
    assert stats.get_retrieval_counts("u") == {"Notes": 1}


def test_a_failed_stats_write_is_logged_not_raised(fake_db, monkeypatch, caplog):
    import memory.retrieval_stats_store as stats

    def boom(*_):
        raise RuntimeError("db down")

    monkeypatch.setattr(stats, "record_retrievals", boom)
    stats.record_retrievals_in_background("u", ["Notes"]).result()
    assert "retrieval stats write failed" in caplog.text
