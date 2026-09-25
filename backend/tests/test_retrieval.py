"""Retrieval helpers: confidence classification, RRF fusion, and the retrieval node."""

import pytest


def _hits(*similarities):
    return [{"id": f"c{i}", "similarity": s} for i, s in enumerate(similarities)]


# --- Confidence --------------------------------------------------------------

@pytest.mark.parametrize("similarities, expected", [
    ((), "low"),
    ((0.1, 0.2), "low"),
    ((0.31, 0.32), "low"),               # only 2 above 0.30
    ((0.31, 0.32, 0.33), "medium"),      # 3 above 0.30
    ((0.5,), "medium"),                  # 1 above 0.45
    ((0.5, 0.6, 0.7), "high"),           # 3 above 0.45
    ((0.46, 0.46, 0.45), "medium"),      # 0.45 itself is not "above"
])
def test_retrieval_confidence_thresholds(similarities, expected):
    from agents.retrieval_agent import _compute_retrieval_confidence

    assert _compute_retrieval_confidence(_hits(*similarities)) == expected


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


@pytest.mark.xfail(strict=True, reason=(
    "known issue: BM25-only hits get a fixed similarity of 0.35, so unrelated "
    "keyword matches count toward 'medium' confidence (fix/retrieval-confidence)"
))
def test_keyword_only_matches_do_not_inflate_confidence():
    from agents.retrieval_agent import _compute_retrieval_confidence
    from memory.vector_store import _rrf_merge

    vector = [{"id": f"v{i}", "similarity": 0.05} for i in range(3)]   # semantically unrelated
    bm25 = [{"id": f"b{i}", "similarity": 0.35} for i in range(3)]     # keyword-only proxies

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
