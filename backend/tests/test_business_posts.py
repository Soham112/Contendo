"""Business context in the pipeline: the profile frame, the BUSINESS POST
block of the draft prompt, and /generate's pillar and pillar_details."""

import pytest

from tests.generation_fixtures import OWN, make_state

ACCOUNT = {
    "segment": "business", "business_niche": "real_estate", "business_niche_other": None,
    "business_profile": {"business_name": "Harbor Street Realty", "service_area": "Portland, Maine",
                         "services": "Homes for first-time buyers.", "tone": "friendly", "tone_notes": "Never pushy."},
}
PROFILE_CHUNK = {"text": "Business name: Harbor Street Realty", "memory_context": "work",
                 "source_type": "business_profile", "source_title": "Business profile", "tags": ""}


# --- Frame --------------------------------------------------------------------

def test_the_profile_note_has_its_own_frame_whatever_its_memory_context():
    from utils.frames import FRAMES, chunk_frame, decide_perspective

    assert chunk_frame(PROFILE_CHUNK, {}) == "BUSINESS_PROFILE"
    assert chunk_frame({**PROFILE_CHUNK, "memory_context": None}, {}) == "BUSINESS_PROFILE"
    assert "BUSINESS_PROFILE" in FRAMES
    # The author's own words about their business, so not "something they read".
    assert decide_perspective([PROFILE_CHUNK], {}) == "experience"


def test_the_profile_frame_rule_reaches_the_prompt_only_with_its_chunk():
    from agents.draft_prompt import build_cited_prompt

    with_profile, _ = build_cited_prompt(make_state([PROFILE_CHUNK, OWN]))
    without, _ = build_cited_prompt(make_state([OWN]))
    assert 'kind="BUSINESS PROFILE"' in with_profile
    assert "Never add a listing, sale, price, client, review, award or result that it does not state." in with_profile
    assert "BUSINESS PROFILE" not in without


# --- business_context ---------------------------------------------------------

def test_business_context_is_none_for_everyone_else():
    from utils.business_notes import business_context

    assert business_context({"segment": None}) is None
    assert business_context({"segment": "individual"}) is None


def test_business_context_carries_tone_and_the_named_pillar():
    from utils.business_notes import business_context

    context = business_context(ACCOUNT, "just_sold")
    assert context["tone"] == "Friendly and approachable. Never pushy."
    assert context["niche_label"] == "Real estate agent"
    assert context["pillar"]["label"] == "Just sold"
    assert business_context(ACCOUNT)["pillar"] is None
    # A pillar of another niche is not this business's.
    assert business_context(ACCOUNT, "menu_highlight")["pillar"] is None


def test_business_context_holds_no_business_facts():
    from utils.business_notes import business_context

    assert "Harbor" not in str(business_context(ACCOUNT, "just_sold"))


# --- Draft prompt -------------------------------------------------------------

@pytest.mark.parametrize("builder", ["cited", "pipeline_a"])
def test_an_individuals_prompt_has_no_business_block(builder):
    from agents.draft_prompt import build_cited_prompt, build_prompt

    state = make_state([OWN])
    prompt = build_cited_prompt(state)[0] if builder == "cited" else build_prompt(state, "chunks")
    assert "BUSINESS POST" not in prompt
    # And it is exactly the prompt an explicit "no business" state gets.
    explicit = make_state([OWN], business=None)
    assert prompt == (build_cited_prompt(explicit)[0] if builder == "cited" else build_prompt(explicit, "chunks"))


def test_a_business_prompt_states_tone_and_pillar():
    from agents.draft_prompt import build_cited_prompt
    from utils.business_notes import business_context

    prompt, _ = build_cited_prompt(make_state([OWN], business=business_context(ACCOUNT, "new_listing")))
    assert "Write it in this tone: Friendly and approachable. Never pushy." in prompt
    assert "Kind of post: New listing. Announces a property that has just come to market." in prompt
    assert "never\ninvent a listing, address, price, review, award, client name or result." in prompt


def test_a_business_prompt_without_a_pillar_has_no_pillar_lines():
    from agents.draft_prompt import build_cited_prompt
    from utils.business_notes import business_context

    prompt, _ = build_cited_prompt(make_state([OWN], business=business_context(ACCOUNT)))
    assert "BUSINESS POST" in prompt
    assert "Kind of post" not in prompt


def test_load_profile_node_sets_business_only_for_a_business(fake_db):
    from pipeline.graph import load_profile_node

    assert "business" not in load_profile_node({"user_id": "user-a"})
    fake_db.tables["accounts"] = [{"user_id": "user-a", **ACCOUNT}]
    state = load_profile_node({"user_id": "user-a", "pillar": "just_sold"})
    assert state["business"]["pillar"]["key"] == "just_sold"


# --- /generate ----------------------------------------------------------------

@pytest.fixture
def a_headers(client, production, auth_headers):
    return auth_headers("user-a")


@pytest.fixture
def pipeline_calls(monkeypatch):
    """Replace run_pipeline in the route; returns the kwargs of each call."""
    import routers.generate as route

    calls = []

    def fake(**kwargs):
        calls.append(kwargs)
        return {"status": "ok", "post": "A post.", "score": 0, "score_feedback": [], "iterations": 1}

    monkeypatch.setattr(route, "run_pipeline", fake)
    return calls


REQUEST = {"topic": "New listing in Maple Heights", "format": "linkedin post", "tone": "casual"}


def test_a_pillar_is_refused_for_a_user_who_is_not_a_business(client, a_headers, pipeline_calls):
    resp = client.post("/generate", headers=a_headers, json={**REQUEST, "pillar": "new_listing"})
    assert resp.status_code == 400
    assert pipeline_calls == []


def test_a_pillar_of_another_niche_is_refused(client, a_headers, fake_db, pipeline_calls):
    fake_db.tables["accounts"] = [{"user_id": "user-a", **ACCOUNT}]
    resp = client.post("/generate", headers=a_headers, json={**REQUEST, "pillar": "menu_highlight"})
    assert resp.status_code == 400
    assert pipeline_calls == []


def test_details_need_a_pillar(client, a_headers, fake_db, pipeline_calls):
    fake_db.tables["accounts"] = [{"user_id": "user-a", **ACCOUNT}]
    resp = client.post("/generate", headers=a_headers, json={**REQUEST, "pillar_details": "Three bedrooms."})
    assert resp.status_code == 400
    assert fake_db.tables.get("embeddings", []) == []


def test_details_are_saved_to_memory_before_the_post_is_drafted(client, a_headers, fake_db, claude, pipeline_calls):
    fake_db.tables["accounts"] = [{"user_id": "user-a", **ACCOUNT}]
    claude.respond_with(lambda kwargs: "[]")
    details = "Three-bedroom semi in Maple Heights with a south-facing garden. Viewings on Saturday."

    resp = client.post("/generate", headers=a_headers,
                       json={**REQUEST, "pillar": "new_listing", "pillar_details": details})

    assert resp.status_code == 200
    rows = fake_db.tables["embeddings"]
    assert rows and all(r["user_id"] == "user-a" and r["source_type"] == "personal_note" for r in rows)
    assert all(r["memory_context"] == "work" for r in rows)
    assert details in rows[0]["content"]
    assert rows[0]["source_title"].startswith("New listing: Three-bedroom semi")
    assert pipeline_calls[0]["pillar"] == "new_listing"


def test_a_plain_request_is_unchanged(client, a_headers, pipeline_calls, claude):
    resp = client.post("/generate", headers=a_headers, json=REQUEST)
    assert resp.status_code == 200
    assert pipeline_calls[0]["pillar"] is None
    assert claude.calls == []
