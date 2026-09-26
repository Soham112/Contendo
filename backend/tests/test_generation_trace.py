"""Generation traces: run_pipeline writes one generation_traces row per run.

Also checks that the retrieval fields added for tracing (chunk_id, bm25_score,
rrf_score, rrf_rank) don't change which chunks are returned or their order.
"""

import copy

import pytest

USER = "user-trace"

# Claude responses for one quality="standard" run, in call order.
STANDARD_RUN = [
    "personal_story",   # draft: archetype (Haiku)
    "Draft text.",      # draft: generate
    "{}",               # critic
    "Humanized text.",  # humanizer
    "CLEAN",            # predictability audit step 1 → skips step 2
    "Audited text.",    # predictability audit step 3
    "Final text.",      # word_count_enforcer: 2 words is under range → expand
]


@pytest.fixture
def seeded_kb():
    from memory.vector_store import upsert_chunks

    # Enough unrelated chunks that BM25's IDF for "pgvector" is positive, so
    # both searches return hits and RRF runs.
    upsert_chunks(
        ["pgvector makes retrieval fast", "unrelated cooking notes",
         "weekend hiking plans", "notes on sourdough starters"],
        source_title="Retrieval notes",
        source_id="src1",
        user_id=USER,
    )


def _run(**overrides):
    from pipeline.graph import run_pipeline

    kwargs = dict(topic="pgvector retrieval", format="linkedin post", tone="casual", user_id=USER)
    kwargs.update(overrides)
    return run_pipeline(**kwargs)


def _only_trace(fake_db):
    rows = fake_db.tables.get("generation_traces", [])
    assert len(rows) == 1
    return rows[0]


# --- The trace row --------------------------------------------------------------

def test_trace_row_has_inputs_and_retrieved_chunks_with_ids_and_text(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)
    result = _run(context="for a talk")

    trace = _only_trace(fake_db)
    assert result["trace_id"] == str(trace["id"])
    assert trace["user_id"] == USER
    assert trace["quality"] == "standard"
    assert trace["length"] == "standard"
    assert trace["retrieval_query"] == "pgvector retrieval. for a talk"
    assert trace["retrieval_path"] == "hybrid"
    assert trace["retrieval_confidence"] in {"low", "medium", "high"}

    top = trace["retrieved"][0]
    assert top["chunk_id"] == "src1_0"
    assert top["text"] == "pgvector makes retrieval fast"
    assert top["source_title"] == "Retrieval notes"
    assert top["rrf_rank"] == 1
    assert top["rrf_score"] > 0
    assert top["bm25_score"] > 0          # found by both searches: BM25 score kept
    assert top["entity_linked"] is False
    assert all(c["chunk_id"] and c["text"] for c in trace["retrieved"])


def test_draft_history_has_one_entry_per_rewriting_node_that_ran(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)
    _run()

    outputs = _only_trace(fake_db)["node_outputs"]
    assert [(d["node"], d["iteration"], d["text"]) for d in outputs["draft_history"]] == [
        ("draft", 0, "Draft text."),
        ("humanizer", 1, "Humanized text."),
        ("predictability_audit", 1, "Audited text."),
        ("word_count_enforcer", 1, "Final text."),
    ]
    assert outputs["final_post"] == "Final text."
    assert outputs["score_history"] == []   # scorer only runs for polished
    assert isinstance(outputs["critic_brief"], dict)


def test_draft_quality_records_only_the_draft(claude, fake_db, seeded_kb):
    claude.queue("personal_story", "Draft text.")
    _run(quality="draft")

    trace = _only_trace(fake_db)
    assert trace["quality"] == "draft"
    assert [d["node"] for d in trace["node_outputs"]["draft_history"]] == ["draft"]


def test_polished_records_a_score_per_iteration(claude, fake_db, seeded_kb, monkeypatch):
    import agents.scorer_agent as scorer_agent

    scores = iter([(60, ["too generic"]), (90, [])])
    monkeypatch.setattr(scorer_agent, "score_text", lambda draft, user_id: next(scores))
    # 2 loops of humanizer + audit (step 1 CLEAN, step 3), then the enforcer.
    claude.queue(
        "personal_story", "Draft text.", "{}",
        "Humanized 1.", "CLEAN", "Audited 1.",
        "Humanized 2.", "CLEAN", "Audited 2.",
        "Final text.",
    )
    _run(quality="polished")

    trace = _only_trace(fake_db)
    assert trace["node_outputs"]["score_history"] == [
        {"iteration": 1, "score": 60, "score_feedback": ["too generic"]},
        {"iteration": 2, "score": 90, "score_feedback": []},
    ]
    assert trace["score"] == 90
    assert trace["iterations"] == 2
    humanized = [d for d in trace["node_outputs"]["draft_history"] if d["node"] == "humanizer"]
    assert [(d["iteration"], d["text"]) for d in humanized] == [(1, "Humanized 1."), (2, "Humanized 2.")]


def test_llm_calls_are_recorded_in_order(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)
    _run()

    calls = _only_trace(fake_db)["llm_calls"]
    assert [c["event_type"] for c in calls] == [
        "archetype", "generate", "critic", "humanize",
        "predictability_audit_step1", "predictability_audit_step3", "word_count_enforcer",
    ]
    assert all(c["input_tokens"] == 10 and c["output_tokens"] == 10 for c in calls)


def test_profile_snapshot_is_stored(claude, fake_db, seeded_kb):
    claude.queue(*STANDARD_RUN)
    _run()

    assert isinstance(_only_trace(fake_db)["profile_snapshot"], dict)


def test_failing_trace_write_still_returns_the_post(claude, fake_db, seeded_kb, monkeypatch, caplog):
    import pipeline.graph as graph

    def boom(row):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(graph, "save_generation_trace", boom)
    claude.queue(*STANDARD_RUN)
    result = _run()

    assert result["post"] == "Final text."
    assert result["trace_id"] is None
    assert "generation trace write failed" in caplog.text


def test_generate_endpoint_returns_trace_id(client, claude, fake_db, seeded_kb, auth_headers):
    claude.queue(*STANDARD_RUN)
    resp = client.post(
        "/generate",
        json={"topic": "pgvector retrieval", "format": "linkedin post", "tone": "casual"},
        headers=auth_headers(USER),
    )

    assert resp.status_code == 200
    assert resp.json()["trace_id"] == str(_only_trace(fake_db)["id"])


def test_flat_fallback_path_is_recorded(claude, fake_db, seeded_kb, monkeypatch):
    import agents.retrieval_agent as retrieval_agent

    def broken_hybrid(*args, **kwargs):
        raise RuntimeError("hybrid down")

    monkeypatch.setattr(retrieval_agent, "query_similar_hybrid", broken_hybrid)
    claude.queue(*STANDARD_RUN)
    _run()

    trace = _only_trace(fake_db)
    assert trace["retrieval_path"] == "flat_fallback"
    assert trace["retrieved"][0]["chunk_id"] == "src1_0"   # vector hits carry their id too


# --- Retrieval output unchanged ------------------------------------------------

_TRACE_KEYS = {"chunk_id", "rrf_score", "rrf_rank"}


def _rrf_merge_before(vector_results, bm25_results, k=60, n_results=8):
    """_rrf_merge exactly as it was before tracing fields were added."""
    combined: dict = {}
    for rank, result in enumerate(vector_results):
        cid = result.get("id") or f"{result.get('source_id')}_{result.get('chunk_index')}"
        entry = combined.setdefault(cid, {"score": 0.0, "result": result})
        entry["score"] += 1.0 / (k + rank + 1)
        entry["result"] = result
    for rank, result in enumerate(bm25_results):
        cid = result.get("id") or f"{result.get('source_id')}_{result.get('chunk_index')}"
        if cid in combined:
            combined[cid]["score"] += 1.0 / (k + rank + 1)
        else:
            combined[cid] = {"score": 1.0 / (k + rank + 1), "result": result}
    merged = sorted(combined.values(), key=lambda e: e["score"], reverse=True)
    return [entry["result"] for entry in merged[:n_results]]


def _strip(chunks, extra=()):
    drop = _TRACE_KEYS | set(extra)
    return [{k: v for k, v in c.items() if k not in drop} for c in chunks]


def test_hybrid_results_and_order_match_the_pre_trace_merge():
    from memory.consolidation_store import upsert_consolidation_chunk
    from memory.vector_store import _query_bm25, query_similar, query_similar_hybrid, upsert_chunks

    upsert_chunks(
        ["pgvector retrieval basics", "retrieval with bm25 ranking",
         "pgvector index tuning", "a note about cooking"],
        source_title="Notes", source_id="notes", user_id=USER,
    )
    # Consolidation chunk: its row id differs from source_id_chunk_index.
    upsert_consolidation_chunk(USER, "ent1", "pgvector", "pgvector retrieval summary")

    query = "pgvector retrieval"
    vector = _strip(query_similar(query, user_id=USER))
    bm25 = [dict(r) for r in _query_bm25(query, user_id=USER)]
    expected = _rrf_merge_before(copy.deepcopy(vector), copy.deepcopy(bm25))

    actual = query_similar_hybrid(query, user_id=USER)

    # Same chunks, same order, same values; only the new trace fields and a
    # BM25 score on shared chunks are added.
    assert _strip(actual, extra={"bm25_score"}) == _strip(expected, extra={"bm25_score"})
    assert [c["rrf_rank"] for c in actual] == list(range(1, len(actual) + 1))


def test_vector_results_only_gain_chunk_id():
    from memory.vector_store import query_similar, upsert_chunks

    upsert_chunks(["pgvector retrieval basics"], source_id="s", user_id=USER)
    [hit] = query_similar("pgvector retrieval", user_id=USER)

    assert hit["chunk_id"] == "s_0"
    assert "id" not in hit   # merge keys for vector hits are unchanged


def test_rrf_copies_bm25_score_onto_shared_chunks_and_ranks_all():
    from memory.vector_store import _rrf_merge

    vector = [{"id": "only-vector", "similarity": 0.9}, {"id": "both", "similarity": 0.5}]
    bm25 = [{"id": "only-bm25", "similarity": 0.35, "bm25_score": 3.0},
            {"id": "both", "similarity": 0.35, "bm25_score": 2.0}]

    merged = {c["id"]: c for c in _rrf_merge(vector, bm25, n_results=3)}

    assert merged["both"]["bm25_score"] == 2.0
    assert merged["both"]["similarity"] == 0.5
    assert "bm25_score" not in merged["only-vector"]
    assert merged["both"]["rrf_rank"] == 1
    assert merged["both"]["rrf_score"] == pytest.approx(1 / 62 + 1 / 62)
    assert sorted(c["rrf_rank"] for c in merged.values()) == [1, 2, 3]


# --- Linking traces to posts via /log-post ----------------------------------------

_LOG_POST = {
    "topic": "t", "format": "linkedin post", "tone": "casual",
    "content": "the post", "authenticity_score": 0,
}


def _seed_trace(fake_db, trace_id, user_id):
    fake_db.tables.setdefault("generation_traces", []).append(
        {"id": trace_id, "user_id": user_id, "post_id": None}
    )


def _trace(fake_db, trace_id):
    return next(t for t in fake_db.tables["generation_traces"] if t["id"] == trace_id)


def test_log_post_links_the_trace_to_the_new_post(client, fake_db, auth_headers):
    _seed_trace(fake_db, "trace-1", USER)

    resp = client.post("/log-post", json={**_LOG_POST, "trace_id": "trace-1"}, headers=auth_headers(USER))

    assert resp.status_code == 200
    assert _trace(fake_db, "trace-1")["post_id"] == resp.json()["post_id"]


def test_log_post_ignores_another_users_trace(client, fake_db, auth_headers, caplog):
    _seed_trace(fake_db, "trace-b", "user-b")

    resp = client.post("/log-post", json={**_LOG_POST, "trace_id": "trace-b"}, headers=auth_headers("user-a"))

    assert resp.status_code == 200
    assert resp.json()["saved"] is True
    assert _trace(fake_db, "trace-b")["post_id"] is None
    assert "not linked" in caplog.text


def test_unknown_trace_id_still_saves_the_post(client, fake_db, auth_headers):
    resp = client.post("/log-post", json={**_LOG_POST, "trace_id": "no-such-trace"}, headers=auth_headers(USER))

    assert resp.status_code == 200
    assert [p["id"] for p in fake_db.tables["posts"]] == [resp.json()["post_id"]]


def test_failing_trace_link_still_saves_the_post(client, fake_db, auth_headers, monkeypatch, caplog):
    import routers.history as history

    def boom(*args, **kwargs):
        raise RuntimeError("invalid input syntax for type uuid")

    monkeypatch.setattr(history, "link_trace_to_post", boom)

    resp = client.post("/log-post", json={**_LOG_POST, "trace_id": "not-a-uuid"}, headers=auth_headers(USER))

    assert resp.status_code == 200
    assert resp.json()["saved"] is True
    assert len(fake_db.tables["post_versions"]) == 1
    assert "linking trace not-a-uuid" in caplog.text


def test_log_post_without_trace_id_does_not_touch_traces(client, fake_db, auth_headers):
    _seed_trace(fake_db, "trace-1", USER)

    resp = client.post("/log-post", json=_LOG_POST, headers=auth_headers(USER))

    assert resp.status_code == 200
    assert resp.json()["saved"] is True
    assert _trace(fake_db, "trace-1")["post_id"] is None
    assert ("generation_traces", "update") not in fake_db.log
