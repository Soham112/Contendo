"""Business fact grounding, gate decisions and retrieval rollback."""
import pytest

from tests.generation_fixtures import OWN, ARTICLE, STORY, make_state
from tests.test_business_posts import ACCOUNT, PROFILE_CHUNK


@pytest.mark.parametrize('pillar,expected', [(None, 'profile_only'), ({'writable_from_profile': True}, 'profile_only'), ({'writable_from_profile': False}, 'low_coverage')])
@pytest.mark.parametrize('first_post,bypass', [(False, False), (True, False), (False, True)])
def test_business_gate_uses_pillar_without_request_word_heuristics(monkeypatch, pillar, expected, first_post, bypass):
    from agents.retrieval_agent import coverage_gate
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1')
    assert coverage_gate([], business={'pillar': pillar}, first_post=first_post, bypass=bypass)['decision'] == expected


def test_business_gate_off_restores_firstpost_and_bypass(monkeypatch):
    from agents.retrieval_agent import coverage_gate
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '0')
    business = {'pillar': {'writable_from_profile': False}}
    assert coverage_gate([], business=business, first_post=True)['decision'] == 'skipped_first_post'
    assert coverage_gate([], business=business, bypass=True)['decision'] == 'bypassed'


def test_only_explicitly_allowed_pillars_are_writable_from_profile():
    from config.niches import NICHES
    allowed = {
        'buyer_seller_tips', 'oral_health_tips', 'treatment_explained',
        'common_questions', 'service_spotlight', 'care_tips', 'trends',
        'maintenance_tips', 'seasonal_reminder', 'service_explained', 'training_tips',
    }
    pillars = [pillar for niche in NICHES for pillar in niche.pillars]
    assert {pillar.key for pillar in pillars if pillar.writable_from_profile} == allowed
    for pillar in pillars:
        assert pillar.writable_from_profile is (pillar.key in allowed)
        assert not hasattr(pillar, 'needs_event')


@pytest.mark.parametrize('pillar_key,writable', [
    ('buyer_seller_tips', True), ('neighborhood_spotlight', False),
])
def test_business_context_exports_profile_writability(pillar_key, writable):
    from utils.business_notes import business_context
    pillar = business_context(ACCOUNT, pillar_key)['pillar']
    assert pillar['writable_from_profile'] is writable
    assert 'needs_event' not in pillar


@pytest.mark.parametrize('writable', [True, False])
def test_covered_business_pillars_pass_regardless_of_profile_writability(monkeypatch, writable):
    from agents.retrieval_agent import coverage_gate
    from config.retrieval import COVERAGE_MIN_COSINE
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1')
    assert coverage_gate(
        [{'similarity': COVERAGE_MIN_COSINE}],
        business={'pillar': {'writable_from_profile': writable}},
    )['decision'] == 'pass'


@pytest.mark.parametrize('chunks,stories', [([PROFILE_CHUNK], False), ([PROFILE_CHUNK, ARTICLE], False), ([PROFILE_CHUNK, OWN], True)])
def test_only_retrieved_own_notes_unlock_stories(monkeypatch, chunks, stories):
    from agents.archetype_agent import structure_offer
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1')
    assert bool(set(structure_offer(make_state(chunks))) & STORY) is stories


@pytest.mark.parametrize('builder', ['cited', 'pipeline_a'])
def test_individual_prompt_bytes_equal_with_flag_on_and_off(monkeypatch, builder):
    from agents.draft_prompt import build_cited_prompt, build_prompt
    def render():
        return build_cited_prompt(make_state([OWN]))[0] if builder == 'cited' else build_prompt(make_state([OWN]), 'chunks')
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '0')
    original = render().encode()
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1')
    assert render().encode() == original


def test_account_name_wins_over_stale_profile_name(monkeypatch):
    from agents.draft_prompt import build_cited_prompt
    from utils.business_notes import business_context
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1')
    renamed = {**ACCOUNT, 'business_profile': {**ACCOUNT['business_profile'], 'business_name': 'New Harbor Realty'}}
    state = make_state([], business=business_context(renamed), profile={'name': 'Old Harbor Realty', 'role': 'Broker', 'voice_descriptors': ['warm']})
    prompt, _ = build_cited_prompt(state)
    assert 'New Harbor Realty' in prompt
    assert 'Old Harbor Realty' not in prompt
    assert 'warm' in prompt
    assert 'BUSINESS FACTS [[B]]' in prompt


def test_business_citation_grounding_uses_only_business_facts():
    from utils.citations import strip_citations, marker
    from pipeline.checks import specific_not_in_cited_source
    stripped = strip_citations('We serve 12 districts. [[B]]')
    span = stripped.spans[0]
    assert span.basis == 'business'
    assert marker(span) == '[[B]]'
    spans = [span.as_dict()]
    assert not specific_not_in_cited_source(spans, {}, [], 'We serve 12 districts.')
    assert specific_not_in_cited_source(spans, {'S1': 'We serve 12 districts.'}, [], 'We serve 3 districts.')
    assert specific_not_in_cited_source(spans, {}, [], '')[0]['type'] == 'citation_unknown_id'


@pytest.mark.parametrize('enabled', [False, True])
def test_all_retrieval_paths_exclude_profile_before_limit_and_restore_on_rollback(monkeypatch, fake_db, enabled):
    from memory.vector_store import query_similar, _fetch_corpus_for_bm25, get_chunks_by_ids
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1' if enabled else '0')
    fake_db.tables['embeddings'] = [
        {'id': 'profile', 'user_id': 'a', 'source_type': 'business_profile', 'content': 'business profile', 'embedding': [1., 0.]},
        {'id': 'legacy', 'user_id': 'a', 'source_type': None, 'content': 'legacy note', 'embedding': [.8, .2]},
        {'id': 'own', 'user_id': 'a', 'source_type': 'personal_note', 'content': 'own note', 'embedding': [.7, .3]},
        {'id': 'other', 'user_id': 'b', 'source_type': 'personal_note', 'content': 'private note', 'embedding': [1., 0.]},
    ]
    vector = query_similar('note', 'a', n_results=1, embedding=[1., 0.])
    assert vector[0]['chunk_id'] == ('legacy' if enabled else 'profile')
    expected = {'legacy', 'own'} if enabled else {'profile', 'legacy', 'own'}
    assert {c['id'] for c in _fetch_corpus_for_bm25('a')} == expected
    assert {c['id'] for c in get_chunks_by_ids(['profile', 'legacy', 'own', 'other'], 'a')} == expected


def test_bm25_cache_rebuilds_when_flag_changes(monkeypatch, fake_db):
    from memory.vector_store import _get_or_build_bm25
    fake_db.tables['embeddings'] = [
        {'id': 'profile', 'user_id': 'a', 'source_type': 'business_profile', 'content': 'profile services'},
        {'id': 'own', 'user_id': 'a', 'source_type': 'personal_note', 'content': 'own event'},
    ]
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '0')
    assert len(_get_or_build_bm25('a')[1]) == 2
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1')
    assert [c['id'] for c in _get_or_build_bm25('a')[1]] == ['own']
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '0')
    assert len(_get_or_build_bm25('a')[1]) == 2


def test_pipeline_a_business_prompt_receives_fact_block(monkeypatch):
    from agents.draft_prompt import build_prompt
    from utils.business_notes import business_context
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '1')
    prompt = build_prompt(make_state([], business=business_context(ACCOUNT)), 'chunks')
    assert 'BUSINESS FACTS [[B]]' in prompt
    assert ACCOUNT['business_profile']['business_name'] in prompt


@pytest.mark.parametrize("enabled", [True, False])
def test_pipeline_identity_comes_from_account_without_overwriting_voice(fake_db, monkeypatch, enabled):
    from pipeline.graph import load_profile_node
    from memory.profile_store import DEFAULT_PROFILE
    monkeypatch.setenv("BUSINESS_BLOCK_ENABLED", "1" if enabled else "0")
    fake_db.tables["accounts"] = [{"user_id": "a", **ACCOUNT}]
    fake_db.tables["profiles"] = [{"id": "a", "data": {**DEFAULT_PROFILE, "name": "Stale name", "voice_descriptors": ["warm"]}}]
    profile = load_profile_node({"user_id": "a"})["profile"]
    assert profile["name"] == (ACCOUNT["business_profile"]["business_name"] if enabled else "Stale name")
    assert profile["voice_descriptors"] == ["warm"]
    assert fake_db.tables["profiles"][0]["data"]["name"] == "Stale name"


def test_profile_only_uses_short_target_and_records_basis():
    from pipeline.graph import plan_node
    from utils.formatters import resolve_length_target
    state = make_state([], coverage_gate={"decision": "profile_only"}, retrieval_confidence="low", first_post=False)
    plan_node(state)
    assert state["length_target"]["basis"] == "profile_only"
    assert state["length_target"]["max_words"] < resolve_length_target("linkedin post", "standard")["max_words"]


@pytest.mark.parametrize('niche,pillar_key', [
    ('real_estate', 'new_listing'),
    ('real_estate', 'neighborhood_spotlight'),
    ('restaurant', 'behind_the_scenes'),
])
def test_source_required_pillar_message_requests_its_needs_even_on_first_post(fake_db, niche, pillar_key):
    from pipeline.graph import run_pipeline
    from config.niches import get_niche
    fake_db.tables['accounts'] = [{'user_id': 'a', **ACCOUNT, 'business_niche': niche}]
    result = run_pipeline(topic='A new listing', format='linkedin post', tone='casual', length='standard',
                          user_id='a', pillar=pillar_key)
    pillar = next(p for p in get_niche(niche).pillars if p.key == pillar_key)
    assert result['status'] == 'low_coverage'
    assert pillar.needs in result['suggestion']


def test_flag_off_restores_profile_story_offer_and_removes_block(monkeypatch):
    from agents.archetype_agent import structure_offer
    from agents.draft_prompt import build_cited_prompt
    from utils.business_notes import business_context
    monkeypatch.setenv('BUSINESS_BLOCK_ENABLED', '0')
    state = make_state([PROFILE_CHUNK], business=business_context(ACCOUNT))
    assert set(structure_offer(state)) & STORY
    assert 'BUSINESS FACTS [[B]]' not in build_cited_prompt(state)[0]
