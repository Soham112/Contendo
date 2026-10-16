"""The segment question: GET /niches, GET /account, PUT /account/segment, skip."""

from datetime import datetime, timedelta, timezone

import pytest

BUSINESS_PROFILE = {
    "business_name": "Harbor Street Realty",
    "service_area": "Portland, Maine",
    "website": "https://example.com",
    "services": "Helping first-time buyers find homes.",
    "tone": "friendly",
    "tone_notes": "",
}


@pytest.fixture
def a_headers(client, production, auth_headers):
    return auth_headers("user-a")


def _business(**overrides) -> dict:
    return {"segment": "business", "business_niche": "real_estate", "business_profile": BUSINESS_PROFILE, **overrides}


def test_niches_is_public_and_lists_real_estate_pillars(client, production):
    resp = client.get("/niches")
    assert resp.status_code == 200
    body = resp.json()
    real_estate = next(n for n in body["niches"] if n["key"] == "real_estate")
    assert [p["key"] for p in real_estate["pillars"]] == [
        "new_listing", "just_sold", "market_update", "neighborhood_spotlight", "buyer_seller_tips", "client_story",
    ]
    assert body["other_niche"] == "other"
    assert body["segments"] == ["business", "individual"]
    assert {t["key"] for t in body["tones"]} >= {"friendly", "professional"}


def test_every_niche_key_is_unique():
    from config import niches

    keys = [n.key for n in niches.NICHES]
    assert len(keys) == len(set(keys))
    for niche in niches.NICHES:
        pillar_keys = [p.key for p in niche.pillars]
        assert len(pillar_keys) == len(set(pillar_keys))


def test_new_user_is_asked_the_segment_question(client, a_headers):
    resp = client.get("/account", headers=a_headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "segment": None, "business_niche": None, "business_niche_other": None,
        "business_profile": None, "ask_segment": True, "memory_saved": None,
    }


def test_account_requires_a_token(client, production):
    assert client.get("/account").status_code == 401
    assert client.put("/account/segment", json={"segment": "individual"}).status_code == 401
    assert client.post("/account/segment/skip").status_code == 401


def test_individual_records_the_segment_only(client, a_headers, fake_db):
    resp = client.put("/account/segment", headers=a_headers, json=_business(segment="individual"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["segment"] == "individual"
    assert body["ask_segment"] is False
    assert body["business_niche"] is None and body["business_profile"] is None
    assert fake_db.tables["accounts"][0]["business_profile"] is None


def test_business_saves_niche_and_profile(client, a_headers):
    resp = client.put("/account/segment", headers=a_headers, json=_business())
    assert resp.status_code == 200
    body = resp.json()
    assert body["segment"] == "business"
    assert body["business_niche"] == "real_estate"
    assert body["business_profile"]["business_name"] == "Harbor Street Realty"
    assert body["business_profile"]["website"] == "https://example.com/"
    assert client.get("/account", headers=a_headers).json() == {**body, "memory_saved": None}


def test_blank_website_is_stored_as_none(client, a_headers):
    profile = {**BUSINESS_PROFILE, "website": "  "}
    resp = client.put("/account/segment", headers=a_headers, json=_business(business_profile=profile))
    assert resp.status_code == 200
    assert resp.json()["business_profile"]["website"] is None


@pytest.mark.parametrize("payload", [
    _business(business_niche="astrologer"),                       # not in the list
    _business(business_niche=None),
    _business(business_profile=None),
    _business(business_niche="other"),                            # no free text
    _business(business_niche="other", business_niche_other="   "),
    _business(business_profile={**BUSINESS_PROFILE, "tone": "sarcastic"}),
    _business(business_profile={**BUSINESS_PROFILE, "business_name": "  "}),
    _business(business_profile={**BUSINESS_PROFILE, "website": "not a url"}),
    {"segment": "agency"},
])
def test_invalid_answers_are_rejected_and_nothing_is_saved(client, a_headers, fake_db, payload):
    resp = client.put("/account/segment", headers=a_headers, json=payload)
    assert resp.status_code == 422
    assert fake_db.tables.get("accounts", []) == []


def test_other_niche_keeps_the_users_own_words(client, a_headers):
    resp = client.put("/account/segment", headers=a_headers,
                      json=_business(business_niche="other", business_niche_other="  Dog groomer "))
    assert resp.status_code == 200
    assert resp.json()["business_niche_other"] == "Dog groomer"


def test_free_text_is_dropped_for_a_listed_niche(client, a_headers):
    resp = client.put("/account/segment", headers=a_headers, json=_business(business_niche_other="ignored"))
    assert resp.json()["business_niche_other"] is None


def test_skip_stops_the_question_until_the_reask_period_passes(client, a_headers, fake_db):
    from memory.account_store import SEGMENT_REASK_DAYS

    resp = client.post("/account/segment/skip", headers=a_headers)
    assert resp.status_code == 200
    assert resp.json()["segment"] is None
    assert resp.json()["ask_segment"] is False

    row = fake_db.tables["accounts"][0]
    row["segment_skipped_at"] = (datetime.now(timezone.utc) - timedelta(days=SEGMENT_REASK_DAYS, minutes=1)).isoformat()
    assert client.get("/account", headers=a_headers).json()["ask_segment"] is True


def test_skipping_after_answering_keeps_the_answer(client, a_headers):
    client.put("/account/segment", headers=a_headers, json=_business())
    resp = client.post("/account/segment/skip", headers=a_headers)
    assert resp.json()["segment"] == "business"
    assert resp.json()["business_niche"] == "real_estate"
    assert resp.json()["ask_segment"] is False


def test_accounts_are_isolated_between_users(client, a_headers, auth_headers):
    client.put("/account/segment", headers=a_headers, json=_business())
    other = client.get("/account", headers=auth_headers("user-b")).json()
    assert other["segment"] is None and other["business_profile"] is None


# --- The business profile as a source in memory ------------------------------

@pytest.fixture
def ingestion(claude):
    """Every ingestion call (tags, entities, summary) answers with an empty list."""
    claude.respond_with(lambda kwargs: "[]")


FULL_PROFILE = {
    **BUSINESS_PROFILE,
    "differentiators": "We answer the phone on Sundays.",
    "typical_customer": "Young families moving out of the city.",
    "current_offers": "Free home valuation this month.",
    "tone_notes": "Never pushy.",
}


def test_business_profile_is_saved_to_memory_as_a_source(client, a_headers, fake_db, ingestion):
    resp = client.put("/account/segment", headers=a_headers, json=_business(business_profile=FULL_PROFILE))
    assert resp.json()["memory_saved"] is True

    rows = fake_db.tables["embeddings"]
    assert {r["user_id"] for r in rows} == {"user-a"}
    assert {r["source_type"] for r in rows} == {"business_profile"}
    assert {r["source_title"] for r in rows} == {"Business profile"}
    note = "\n".join(r["content"] for r in rows)
    for stated in ("Real estate agent", "Harbor Street Realty", "Portland, Maine", "https://example.com/",
                   "first-time buyers", "Sundays", "Young families", "Free home valuation"):
        assert stated in note
    # Tone is voice, not content.
    assert "pushy" not in note and "Friendly" not in note


def test_saving_the_profile_again_replaces_the_note(client, a_headers, fake_db, ingestion):
    client.put("/account/segment", headers=a_headers, json=_business())
    renamed = {**BUSINESS_PROFILE, "business_name": "Quay Lane Homes"}
    client.put("/account/segment", headers=a_headers, json=_business(business_profile=renamed))

    note = "\n".join(r["content"] for r in fake_db.tables["embeddings"])
    assert "Quay Lane Homes" in note
    assert "Harbor Street Realty" not in note


def test_saving_the_profile_again_updates_its_one_sources_row(client, a_headers, fake_db, ingestion):
    client.put("/account/segment", headers=a_headers, json=_business())
    [first] = fake_db.tables["sources"]
    renamed = {**BUSINESS_PROFILE, "business_name": "Quay Lane Homes"}
    client.put("/account/segment", headers=a_headers, json=_business(business_profile=renamed))

    [row] = fake_db.tables["sources"]
    assert row["source_id"] == first["source_id"] and row["status"] == "ready"
    assert "Quay Lane Homes" in row["extracted_text"]
    assert row["raw_json"]["business_profile"]["business_name"] == "Quay Lane Homes"
    assert (row["input_type"], row["authorship"], row["authorship_set_by"]) == ("business_profile", "user_stated", "rule")
    assert {r["source_id"] for r in fake_db.tables["embeddings"]} == {row["source_id"]}


def test_other_niche_note_uses_the_users_own_words(client, a_headers, fake_db, ingestion):
    client.put("/account/segment", headers=a_headers,
               json=_business(business_niche="other", business_niche_other="Dog groomer"))
    assert "Kind of business: Dog groomer" in fake_db.tables["embeddings"][0]["content"]


def test_a_failed_note_still_saves_the_answer_and_says_so(client, a_headers, fake_db):
    # No Claude reply is queued, so ingestion fails.
    resp = client.put("/account/segment", headers=a_headers, json=_business())
    assert resp.status_code == 200
    assert resp.json()["segment"] == "business"
    assert resp.json()["memory_saved"] is False


def test_individual_adds_nothing_to_memory(client, a_headers, fake_db, claude):
    resp = client.put("/account/segment", headers=a_headers, json={"segment": "individual"})
    assert resp.json()["memory_saved"] is None
    assert fake_db.tables.get("embeddings", []) == []
    assert claude.calls == []


def test_a_new_business_user_gets_a_voice_profile_named_after_the_business(client, a_headers, fake_db, ingestion):
    client.put("/account/segment", headers=a_headers, json=_business())
    profile = client.get("/profile", headers=a_headers).json()
    assert profile["has_profile"] is True
    assert profile["profile"]["name"] == "Harbor Street Realty"
    assert profile["profile"]["role"] == "Real estate agent"
    assert profile["profile"]["location"] == "Portland, Maine"


def test_an_existing_voice_profile_is_left_alone(client, a_headers, fake_db, ingestion):
    fake_db.tables["profiles"] = [{"id": "user-a", "data": {"name": "Mara", "role": "Agent", "voice_descriptors": ["dry"]}}]
    client.put("/account/segment", headers=a_headers, json=_business())
    profile = client.get("/profile", headers=a_headers).json()["profile"]
    assert profile["name"] == "Mara" and profile["voice_descriptors"] == ["dry"]
