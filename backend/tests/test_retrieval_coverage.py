"""BM25 tokenization, fusion keys, real similarity for BM25 hits, and the coverage gate."""

import pytest

USER = "user-coverage"


# --- tokenizer -----------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    # The eval's off-topic queries matched chunks only on these function words.
    ("Lessons from training for my first marathon", ["training", "marathon"]),
    ("My favourite hiking trails in the Lake District", ["favourite", "hiking", "trail", "lake", "district"]),
    ("Autoscaling Kubernetes clusters for GPU inference", ["autoscaling", "kubernete", "cluster", "gpu", "inference"]),
    ("Data contracts: cheaper than incidents!", ["data", "contract", "cheaper", "incident"]),
    ("the team's stories, classes and boxes", ["team", "story", "class", "box"]),
    ("analysis of the boss's status", ["analysis", "boss", "status"]),
])
def test_tokenize_drops_stop_words_and_punctuation_and_folds_plurals(text, expected):
    from memory.vector_store import _tokenize

    assert _tokenize(text) == expected


def test_tokenize_returns_nothing_for_stop_words_only():
    from memory.vector_store import _tokenize

    assert _tokenize("for the first time in my life, from here") == ["time", "life"]
    assert _tokenize("for the in from first") == []


# --- BM25 --------------------------------------------------------------------------

@pytest.fixture
def kb():
    from memory.vector_store import invalidate_bm25_cache, upsert_chunks

    upsert_chunks(
        ["Data contracts between teams stop upstream schema changes from breaking ingestion.",
         "Notes on sourdough starters and the first loaf I baked for my family.",
         "Feature store migration took eleven weeks of definition arguments.",
         "Weekend hiking plans in the hills."],
        source_title="Notes", source_id="kb", user_id=USER,
    )
    invalidate_bm25_cache(USER)


def test_bm25_does_not_match_on_stop_words(kb):
    from memory.vector_store import _query_bm25

    # Before the fix, "for", "my" and "first" matched the sourdough note.
    assert _query_bm25("Lessons from training for my first marathon", USER) == []


def test_bm25_hits_carry_a_normalized_score_and_no_proxy_similarity(kb):
    from memory.vector_store import _query_bm25

    [top, *_] = _query_bm25("data contracts", USER)
    assert top["source_id"] == "kb" and top["chunk_index"] == 0
    assert 0 < top["bm25_norm"] <= 1
    assert "similarity" not in top


def test_bm25_norm_is_lower_when_distinctive_query_words_are_missing(kb):
    from memory.vector_store import _query_bm25

    covered = _query_bm25("data contracts", USER)[0]["bm25_norm"]
    partly = _query_bm25("data contracts marathon kubernetes", USER)[0]["bm25_norm"]
    assert partly < covered / 2


# --- fusion and similarity ----------------------------------------------------------

def test_rrf_merges_a_consolidation_chunk_found_by_both_searches():
    from memory.vector_store import _rrf_merge

    row_id = "consolidation_u_ent1"
    vector = [{"chunk_id": row_id, "source_id": "ent1", "chunk_index": 0, "similarity": 0.6}]
    bm25 = [{"id": row_id, "source_id": "ent1", "chunk_index": 0, "bm25_score": 2.0, "bm25_norm": 0.4}]

    [merged] = _rrf_merge(vector, bm25)
    assert merged["similarity"] == 0.6
    assert merged["bm25_norm"] == 0.4
    assert merged["rrf_score"] == pytest.approx(2 / 61)


def test_bm25_only_hits_get_their_real_cosine_similarity(kb):
    from memory.vector_store import query_similar, query_similar_hybrid

    query = "upstream schema ingestion"
    hits = query_similar_hybrid(query, USER, n_results=8)
    cosine = {h["chunk_id"]: h["similarity"] for h in query_similar(query, USER, n_results=50)}
    assert hits
    for h in hits:
        assert h["similarity"] == pytest.approx(cosine[h.get("chunk_id") or h.get("id")], abs=1e-3)


# --- coverage gate --------------------------------------------------------------------

def _r(title, similarity, bm25_norm=None, text="chunk text"):
    hit = {"source_title": title, "similarity": similarity, "text": text}
    if bm25_norm is not None:
        hit["bm25_norm"] = bm25_norm
    return hit


@pytest.mark.parametrize("results, bypass, decision", [
    ([_r("A", 0.30)], False, "pass"),                       # cosine at the threshold
    ([_r("A", 0.28, bm25_norm=0.45)], False, "pass"),       # ds-02: rescued by a strong keyword hit
    ([_r("A", 0.26, bm25_norm=0.07)], False, "low_coverage"),  # ds-07
    ([_r("A", 0.29), _r("B", 0.29, bm25_norm=0.29)], False, "low_coverage"),
    ([], False, "low_coverage"),
    ([_r("A", 0.10)], True, "bypassed"),
    ([_r("A", 0.50)], True, "pass"),                         # bypass only matters when blocked
])
def test_coverage_gate_decision(results, bypass, decision):
    from agents.retrieval_agent import coverage_gate

    assert coverage_gate(results, bypass=bypass)["decision"] == decision


def test_coverage_gate_lists_the_closest_distinct_sources():
    from agents.retrieval_agent import coverage_gate

    gate = coverage_gate([
        _r("B", 0.12, text="b" * 300), _r("A", 0.25), _r("A", 0.20), _r("C", 0.05), _r("D", 0.01),
    ])
    assert [s["title"] for s in gate["closest_sources"]] == ["A", "B", "C"]
    assert gate["closest_sources"][1]["preview"] == "b" * 200
    assert gate["top_cosine"] == 0.25


@pytest.mark.parametrize("chunk, keep", [
    (_r("A", 0.30), True),
    (_r("A", 0.28, bm25_norm=0.45), True),
    (_r("A", 0.28, bm25_norm=0.10), False),
    (_r("A", 0.0), False),
])
def test_chunks_are_kept_on_cosine_or_a_strong_keyword_match(chunk, keep):
    from agents.retrieval_agent import _is_relevant

    assert _is_relevant(chunk) is keep


# --- pipeline and endpoint -------------------------------------------------------------

@pytest.fixture
def pgvector_kb(fake_db):
    from memory.vector_store import invalidate_bm25_cache, upsert_chunks

    upsert_chunks(
        ["pgvector makes retrieval fast", "unrelated cooking notes",
         "weekend hiking plans", "notes on sourdough starters"],
        source_title="Retrieval notes", source_id="src1", user_id=USER,
    )
    invalidate_bm25_cache(USER)
    # One earlier post, so these runs are not the user's first post (which skips the gate).
    fake_db.tables.setdefault("posts", []).append(
        {"id": 1, "user_id": USER, "topic": "An earlier post", "created_at": "2026-09-01T00:00:00+00:00"}
    )


def _run(**kwargs):
    from pipeline.graph import run_pipeline

    args = dict(topic="Kubernetes GPU autoscaling", format="linkedin post", tone="casual", user_id=USER)
    args.update(kwargs)
    return run_pipeline(**args)


def test_low_coverage_stops_before_drafting(claude, fake_db, pgvector_kb):
    result = _run()  # no Claude responses queued: any drafting call would fail the test

    assert claude.calls == []
    assert result["status"] == "low_coverage"
    assert result["post"] == ""
    assert result["closest_sources"] and result["suggestion"]
    [trace] = fake_db.tables["generation_traces"]
    assert trace["node_outputs"]["coverage_gate"]["decision"] == "low_coverage"
    assert trace["node_outputs"]["final_post"] == ""
    assert trace["retrieval_confidence"] == "low"


def test_no_specifics_bypasses_the_gate(claude, fake_db, pgvector_kb, no_specifics_on):
    claude.queue("personal_story", "Draft text.", "{}", "Humanized text.", "CLEAN", "Audited text.", "Final text.")
    result = _run(no_specifics=True)

    assert result["status"] == "ok"
    assert result["post"]
    [trace] = fake_db.tables["generation_traces"]
    assert trace["node_outputs"]["coverage_gate"]["decision"] == "bypassed"


def test_covered_topic_passes_the_gate(claude, fake_db, pgvector_kb):
    claude.queue("personal_story", "Draft text.", "{}", "Humanized text.", "CLEAN", "Audited text.", "Final text.")
    result = _run(topic="pgvector retrieval")

    assert result["status"] == "ok"
    [trace] = fake_db.tables["generation_traces"]
    assert trace["node_outputs"]["coverage_gate"]["decision"] == "pass"


def test_generate_endpoint_returns_low_coverage(client, claude, fake_db, pgvector_kb, auth_headers):
    response = client.post(
        "/generate",
        json={"topic": "Kubernetes GPU autoscaling", "format": "linkedin post", "tone": "casual"},
        headers=auth_headers(USER),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "low_coverage"
    assert body["post"] == ""
    assert body["closest_sources"][0].keys() == {"title", "preview", "similarity"}
    assert body["no_specifics_enabled"] is False  # the notice hides the opinion-post option
    assert claude.calls == []


def test_generate_rejects_no_specifics_while_the_mode_is_disabled(client, claude, fake_db, pgvector_kb, auth_headers):
    response = client.post(
        "/generate",
        json={"topic": "Kubernetes GPU autoscaling", "format": "linkedin post", "tone": "casual",
              "no_specifics": True},
        headers=auth_headers(USER),
    )
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Opinion posts without specifics are turned off for now.")
    assert claude.calls == [] and fake_db.tables.get("generation_traces", []) == []


def test_run_pipeline_refuses_no_specifics_while_the_mode_is_disabled(claude, fake_db, pgvector_kb):
    with pytest.raises(ValueError, match="no-specifics mode is disabled"):
        _run(no_specifics=True)
    assert claude.calls == []


def test_generate_accepts_no_specifics_when_the_mode_is_enabled(client, claude, fake_db, pgvector_kb, auth_headers,
                                                                no_specifics_on):
    claude.queue("personal_story", "Draft text.", "{}", "Humanized text.", "CLEAN", "Audited text.", "Final text.", "[]")
    response = client.post(
        "/generate",
        json={"topic": "Kubernetes GPU autoscaling", "format": "linkedin post", "tone": "casual",
              "no_specifics": True},
        headers=auth_headers(USER),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok" and response.json()["no_specifics_enabled"] is True


def test_coverage_gate_skips_a_users_first_post():
    from agents.retrieval_agent import coverage_gate

    assert coverage_gate([_r("A", 0.05)], first_post=True)["decision"] == "skipped_first_post"
    assert coverage_gate([_r("A", 0.50)], first_post=True)["decision"] == "pass"
    assert coverage_gate([_r("A", 0.05)], bypass=True, first_post=True)["decision"] == "bypassed"


def test_first_post_with_an_empty_knowledge_base_is_still_drafted(claude, fake_db):
    # A new user: no sources and no saved posts. Onboarding must still produce a post.
    claude.queue("personal_story", "Draft text.", "{}", "Humanized text.", "CLEAN", "Audited text.", "Final text.")
    result = _run(user_id="brand-new-user", topic="Why I moved from analytics to ML")

    assert result["status"] == "ok"
    assert result["post"]
    [trace] = fake_db.tables["generation_traces"]
    assert trace["node_outputs"]["coverage_gate"]["decision"] == "skipped_first_post"


# --- entity-linked chunks -----------------------------------------------------------

@pytest.fixture
def entity_kb(fake_db):
    from memory.vector_store import invalidate_bm25_cache, upsert_chunks

    # Chunks that never match the query directly, linked to the entity "kestrel".
    upsert_chunks(
        ["weekly retraining kept the plan stable", "depot managers lost trust in jumpy numbers",
         "sourdough starter notes"],
        source_title="Kestrel notes", source_id="kes", user_id=USER,
    )
    invalidate_bm25_cache(USER)
    fake_db.tables.setdefault("entities", []).append(
        {"entity_id": "e1", "user_id": USER, "entity_name": "kestrel", "entity_type": "project"})
    fake_db.tables.setdefault("chunk_entities", []).extend(
        {"chunk_id": f"kes_{i}", "entity_id": "e1", "user_id": USER, "relationship_type": "mentions"}
        for i in (0, 1))


def test_entity_linked_chunks_get_real_similarity_not_a_proxy(entity_kb):
    from agents.retrieval_agent import _enrich_with_entity_chunks
    from memory.vector_store import query_similar

    query = "kestrel retraining plan"
    added = [c for c in _enrich_with_entity_chunks([], query, USER) if c.get("entity_linked")]
    cosine = {h["chunk_id"]: h["similarity"] for h in query_similar(query, USER, n_results=50)}

    assert {c["id"] for c in added} == {"kes_0", "kes_1"}
    for c in added:
        assert c["similarity"] != 0.35
        assert c["similarity"] == pytest.approx(cosine[c["id"]], abs=1e-3)
    assert [c["similarity"] for c in added] == sorted((c["similarity"] for c in added), reverse=True)


def test_entity_linked_chunks_do_not_count_toward_confidence_or_the_gate(entity_kb, fake_db):
    from agents.retrieval_agent import _compute_retrieval_confidence, coverage_gate, retrieval_node
    from memory.vector_store import query_similar_hybrid

    fake_db.tables.setdefault("posts", []).append(
        {"id": 1, "user_id": USER, "topic": "An earlier post", "created_at": "2026-09-01T00:00:00+00:00"})
    topic = "What kestrel taught me about volcanoes"  # names the entity; no chunk matches the words
    state = retrieval_node({"topic": topic, "user_id": USER})

    assert any(c.get("entity_linked") for c in state["retrieval_bundle"]["chunks"])  # still added for drafting
    direct = query_similar_hybrid(topic, USER, n_results=8)
    assert state["coverage_gate"] == coverage_gate(direct)
    assert state["retrieval_confidence"] == _compute_retrieval_confidence(direct)


# --- no-specifics mode -------------------------------------------------------------

STANDARD = ["personal_story", "Draft text.", "{}", "Humanized text.", "CLEAN", "Audited text.", "Final text."]


def _generate_prompt(claude):
    return claude.calls[1]["messages"][-1]["content"]  # call 0 is the archetype, call 1 the draft


def test_drafter_gets_the_no_specifics_rule_only_in_that_mode(claude, fake_db, pgvector_kb, no_specifics_on):
    claude.queue(*STANDARD)
    _run(no_specifics=True)
    prompt = _generate_prompt(claude)
    assert "NO-SPECIFICS RULE (highest priority" in prompt
    assert "unless it appears in the topic or the additional context above" in prompt

    claude.reset()
    fake_db.tables["generation_traces"].clear()
    claude.queue(*STANDARD)
    _run(topic="pgvector retrieval")
    assert "NO-SPECIFICS RULE" not in _generate_prompt(claude)


def test_no_specifics_grounding_is_topic_context_and_profile_only():
    from utils.specifics import grounding_texts, unsupported_specifics

    state = {
        "no_specifics": True,
        "topic": "Why 2024 was hard",
        "context": "we cut churn 40%",
        "profile": {"bio": "Seven years in data"},
        "retrieval_bundle": {"chunks": [{"text": "migration took eleven weeks"}]},
        "retrieved_chunks": ["[source_type: note] 61 percent adoption"],
    }
    sources = grounding_texts(state, "the draft mentions 12 clinics")
    assert unsupported_specifics("2024, 40%, seven years", sources) == []
    assert [s.text for s in unsupported_specifics("eleven weeks, 61 percent, 12 clinics", sources)] == [
        "eleven weeks", "61 percent", "12",
    ]


def test_humanizer_in_no_specifics_mode_rejects_chunk_facts_with_the_opinion_retry(claude):
    from agents.humanizer_agent import humanizer_node

    state = {
        "quality": "standard", "user_id": USER, "format": "thread", "length": "standard",
        "no_specifics": True, "topic": "Data contracts", "context": "",
        "profile": {"name": "Mara", "role": "Data scientist", "bio": "Seven years in data science"},
        "retrieval_bundle": {"chunks": [{"text": "For six days Kestrel saw zero bookings."}]},
        "critic_brief": {}, "current_draft": "Data contracts are cheaper than outages.",
        "iterations": 0, "draft_history": [],
    }
    claude.queue("For six days we saw zero bookings. Contracts are cheaper.",   # chunk fact: rejected
                 "In seven years I have learned contracts are cheaper than outages.")  # profile fact: fine
    state = humanizer_node(state)

    retry_prompt = claude.calls[1]["messages"][-1]["content"]
    assert "This is an opinion post without specifics." in retry_prompt
    assert "- six days" in retry_prompt.lower() or "- for six days" in retry_prompt.lower()
    assert state["current_draft"] == "In seven years I have learned contracts are cheaper than outages."
    assert state["specifics_guard"][0]["outcome"] == "accepted_after_retry"


def test_retry_note_wording_by_mode():
    from utils.specifics import extract_specifics, retry_note

    v = extract_specifics("34%")
    assert "not in the draft or its sources" in retry_note(v)
    assert "not in the topic, the context or the author profile" in retry_note(v, no_specifics=True)
    assert retry_note([], no_specifics=True) == ""
