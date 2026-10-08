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
