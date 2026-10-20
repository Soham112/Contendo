"""Provenance step 3.3 wiring: chunk offsets, spans onto chunks, the classifier
at ingest, PATCH /sources/{id}/authorship, and the backfill. The classifier's
answers are faked (two samples per part); nothing here judges labelling quality."""
import json
import re

import pytest

from memory.source_store import typed_text
from utils.chunker import CHUNK_SIZE_WORDS, OVERLAP_WORDS, chunk_spans, chunk_text
from utils.provenance_spans import chunk_labels, paragraphs

USER = "user-prov"
OTHER = "user-other"
TOOL = "record_provenance"

OWN_NOTE = ("I took 200 real tickets from our design partner and compared replies by hand.\n\n"
            "It took me six hours a week, every Friday.") * 1
# Three paragraphs, 300 + 100 + 300 words: chunk 0 is words 0-499 (touches the
# middle paragraph), chunk 1 is words 450-699 (the last paragraph only).
MIXED = "\n\n".join([" ".join(f"own{i}" for i in range(300)),
                     " ".join(f"quoted{i}" for i in range(100)),
                     " ".join(f"my{i}" for i in range(300))])


def reading(authorship="user_authored", other=(), quotes=("own1 own2",), uncertain=False) -> str:
    return json.dumps({"reasoning": "who speaks", "authorship": authorship, "other_paragraphs": list(other),
                       "evidence_quotes": list(quotes), "source_facts_used": [], "uncertain": uncertain})


def _is_provenance(kw: dict) -> bool:
    return (kw.get("tool_choice") or {}).get("name") == TOOL


def answer(claude, *provenance_replies) -> list[dict]:
    """Classifier calls get these replies in turn (the last one repeats; a
    callable is given the request); every other ingestion call gets "[]".
    Returns the list of classifier calls."""
    seen: list[dict] = []

    def respond(kw):
        if not _is_provenance(kw):
            return "[]"
        seen.append(kw)
        reply = provenance_replies[min(len(seen), len(provenance_replies)) - 1]
        return reply(kw) if callable(reply) else reply
    claude.respond_with(respond)
    return seen


def own_reading(kw: dict) -> str:
    """A confident user_authored reading quoting whichever fixture was sent."""
    message = kw["messages"][0]["content"]
    return reading(quotes=["own1 own2"] if "own1 own2" in message else ["It took me six hours a week"])


def _ingest(text, *, user_id=USER, original=None, **kw):
    from agents.ingestion_agent import ingest_content
    return ingest_content(text, source_type="personal_note", user_id=user_id,
                          original=original or typed_text(text=text, title_provided=False), **kw)


def _source(fake_db, user_id=USER):
    [row] = [r for r in fake_db.tables.get("sources", []) if r["user_id"] == user_id]
    return row


def _chunk_labels(fake_db, source_id, user_id=USER):
    rows = [r for r in fake_db.tables.get("embeddings", [])
            if r["source_id"] == source_id and r["user_id"] == user_id]
    return [r.get("chunk_authorship") for r in sorted(rows, key=lambda r: r["chunk_index"])]


# --- Chunk offsets -------------------------------------------------------------------------------

def _old_chunk_text(text: str) -> list[str]:
    """The chunker before offsets (whitespace collapsed, then words), to prove chunks are unchanged."""
    words = re.sub(r"\s+", " ", text.strip()).split()
    if len(words) <= CHUNK_SIZE_WORDS:
        return [" ".join(words)] if words else []
    out, start = [], 0
    while start < len(words):
        out.append(" ".join(words[start:start + CHUNK_SIZE_WORDS]))
        if start + CHUNK_SIZE_WORDS >= len(words):
            break
        start += CHUNK_SIZE_WORDS - OVERLAP_WORDS
    return out


@pytest.mark.parametrize("text", [
    "", "   \n\t ", "one", OWN_NOTE, MIXED,
    "a b c\x1cd　e​f\tg\r\nh",          # unicode whitespace; ​ is not whitespace
    " ".join(f"w{i}" for i in range(1_249)),
    "\n\n".join(" ".join(f"p{j}x{i}" for i in range(137)) for j in range(9)),
])
def test_chunks_are_unchanged_and_offsets_slice_their_words(text):
    spans = chunk_spans(text)
    assert chunk_text(text) == _old_chunk_text(text)
    for chunk in spans:
        assert " ".join(text[chunk.start:chunk.end].split()) == chunk.text
        assert not text[chunk.start].isspace() and not text[chunk.end - 1].isspace()


# --- Spans onto chunks ---------------------------------------------------------------------------

def test_any_overlap_with_an_external_passage_makes_a_chunk_of_an_own_source_external():
    spans = [{"start": 100, "end": 200, "authorship": "external"}]
    chunks = [(0, 100), (0, 101), (150, 160), (199, 300), (200, 300)]
    assert chunk_labels(chunks, "user_authored", spans) == [None, "external", "external", "external", None]


def test_a_chunk_of_an_external_source_is_own_only_when_own_passages_cover_it():
    spans = [{"start": 0, "end": 100, "authorship": "user_authored"},
             {"start": 100, "end": 180, "authorship": "user_authored"},
             {"start": 190, "end": 300, "authorship": "user_authored"}]
    chunks = [(10, 90), (50, 170), (150, 200), (195, 300), (250, 310)]
    assert chunk_labels(chunks, "external", spans) == ["user_authored", "user_authored", None, "user_authored", None]


def test_spans_with_the_source_label_and_rule_or_missing_labels_give_no_chunk_labels():
    own = [{"start": 0, "end": 50, "authorship": "user_authored"}]
    assert chunk_labels([(0, 50)], "user_authored", own) == [None]
    for label in ("user_stated", "system_inferred", None):
        assert chunk_labels([(0, 50)], label, [{"start": 0, "end": 50, "authorship": "external"}]) == [None]


# --- At ingest -----------------------------------------------------------------------------------

def test_confident_reading_is_written_with_its_detail(fake_db, claude):
    calls = answer(claude, reading(quotes=["It took me six hours a week"]))
    result = _ingest(OWN_NOTE)
    row = _source(fake_db)
    assert len(calls) == 2
    assert result["authorship"] == "user_authored"
    assert (row["authorship"], row["authorship_set_by"]) == ("user_authored", "classifier")
    assert row["authorship_detail"]["classifier"]["confident"] is True
    assert row["authorship_detail"]["spans"] == []
    assert _chunk_labels(fake_db, row["source_id"]) == [None]


def test_the_classifier_sees_the_source_facts(fake_db, claude):
    calls = answer(claude, reading(quotes=["It took me six hours a week"]))
    _ingest(OWN_NOTE, source_title="Friday reviews",
            original=typed_text(text=OWN_NOTE, title_provided=True))
    message = calls[0]["messages"][0]["content"]
    assert "Friday reviews" in message and "personal_note" in message


def test_mixed_source_marks_the_chunk_that_touches_the_outside_passage(fake_db, claude):
    answer(claude, reading(other=[2], quotes=["own1 own2"]))
    _ingest(MIXED)
    row = _source(fake_db)
    [span] = row["authorship_detail"]["spans"]
    assert span["authorship"] == "external" and MIXED[span["start"]:span["end"]].startswith("quoted0")
    assert _chunk_labels(fake_db, row["source_id"]) == ["external", None]


def test_disagreeing_samples_leave_authorship_unknown_but_keep_the_detail(fake_db, claude):
    answer(claude, reading(quotes=["own1 own2"]), reading("external", quotes=["own1 own2"]))
    result = _ingest(MIXED)
    row = _source(fake_db)
    assert result["authorship"] is None
    assert (row["authorship"], row["authorship_set_by"]) == (None, None)
    assert row["authorship_detail"]["classifier"]["confident"] is False
    assert _chunk_labels(fake_db, row["source_id"]) == [None, None]


def test_no_valid_answer_or_an_api_error_never_fails_ingestion(fake_db, claude, monkeypatch):
    answer(claude, "not json")
    assert _ingest(OWN_NOTE)["chunks_stored"] == 1
    assert _source(fake_db)["authorship_detail"] is None

    import agents.ingestion_agent as agent

    def boom(*a, **k):
        raise RuntimeError("api down")
    monkeypatch.setattr(agent, "classify_provenance", boom)
    assert _ingest(MIXED, user_id=OTHER)["chunks_stored"] == 2
    assert _source(fake_db, OTHER)["authorship"] is None


def test_a_rule_label_skips_the_classifier(fake_db, claude):
    calls = answer(claude, reading())
    original = typed_text("business_profile", text=OWN_NOTE, title_provided=True,
                          authorship="user_stated", authorship_set_by="rule")
    _ingest(OWN_NOTE, original=original)
    row = _source(fake_db)
    assert calls == []
    assert (row["authorship"], row["authorship_set_by"]) == ("user_stated", "rule")


# --- PATCH /sources/{id}/authorship and Replace --------------------------------------------------

@pytest.fixture
def headers(client, production, auth_headers):
    return auth_headers(USER)


def _patch(client, headers, source_id, authorship):
    return client.patch(f"/sources/{source_id}/authorship", json={"authorship": authorship}, headers=headers)


def test_users_choice_keeps_differing_passages_and_relabels_chunks(fake_db, claude, client, headers):
    answer(claude, reading(other=[2], quotes=["own1 own2"]))
    _ingest(MIXED)
    sid = _source(fake_db)["source_id"]

    resp = _patch(client, headers, sid, "user_authored")       # confirm: the quote stays external
    assert resp.status_code == 200 and resp.json()["spans_mapped"] is True
    assert (_source(fake_db)["authorship"], _source(fake_db)["authorship_set_by"]) == ("user_authored", "user")
    assert _chunk_labels(fake_db, sid) == ["external", None]

    assert _patch(client, headers, sid, "external").status_code == 200   # flip: everything external
    assert _source(fake_db)["authorship"] == "external"
    assert _chunk_labels(fake_db, sid) == [None, None]


def test_users_choice_on_an_unknown_source_uses_the_classifiers_passages(fake_db, claude, client, headers):
    # Paragraphs 1-2 external (400 words), 3 own; uncertain, so not applied.
    answer(claude, reading("external", other=[3], quotes=["own1 own2"], uncertain=True))
    _ingest(MIXED)
    sid = _source(fake_db)["source_id"]
    assert _source(fake_db)["authorship"] is None
    assert _chunk_labels(fake_db, sid) == [None, None]
    assert _patch(client, headers, sid, "external").status_code == 200
    # Chunk 1 lies inside paragraph 3; chunk 0 spans paragraphs 1 and 2.
    assert _chunk_labels(fake_db, sid) == [None, "user_authored"]


def test_patch_checks_ownership_and_the_allowed_labels(fake_db, claude, client, headers, auth_headers):
    answer(claude, reading(quotes=["It took me six hours a week"]))
    _ingest(OWN_NOTE)
    sid = _source(fake_db)["source_id"]
    assert _patch(client, auth_headers(OTHER), sid, "external").status_code == 404
    assert _patch(client, headers, "missing", "external").status_code == 404
    assert _patch(client, headers, sid, "user_stated").status_code == 422
    assert _patch(client, headers, sid, "system_inferred").status_code == 422
    assert _source(fake_db)["authorship_set_by"] == "classifier"


def test_patch_waits_for_a_running_replace(fake_db, claude, client, headers):
    answer(claude, reading(quotes=["It took me six hours a week"]))
    _ingest(OWN_NOTE)
    row = _source(fake_db)
    row["pending_replace"] = {"ingest_id": "new"}
    assert _patch(client, headers, row["source_id"], "external").status_code == 409
    assert row["authorship_set_by"] == "classifier"


def test_replace_keeps_the_users_choice_and_skips_the_classifier(fake_db, claude, client, headers):
    answer(claude, reading(quotes=["It took me six hours a week"]))
    _ingest(OWN_NOTE)
    sid = _source(fake_db)["source_id"]
    assert _patch(client, headers, sid, "external").status_code == 200

    calls = answer(claude, reading())
    _ingest(MIXED, replace_source_id=sid)
    row = _source(fake_db)
    assert calls == []
    assert (row["authorship"], row["authorship_set_by"]) == ("external", "user")
    assert _chunk_labels(fake_db, sid) == [None, None]


def test_replace_of_a_classifier_label_reads_the_new_text(fake_db, claude):
    answer(claude, reading(quotes=["It took me six hours a week"]))
    _ingest(OWN_NOTE)
    sid = _source(fake_db)["source_id"]
    calls = answer(claude, reading(other=[2], quotes=["own1 own2"]))
    _ingest(MIXED, replace_source_id=sid)
    assert len(calls) == 2
    assert _chunk_labels(fake_db, sid) == ["external", None]


# --- Backfill ------------------------------------------------------------------------------------

def _stored(fake_db, claude, text, user_id=USER, context=None):
    """A source as stored before step 3.3: no authorship, no detail."""
    answer(claude, "not json")
    _ingest(text, user_id=user_id, memory_context=context)
    row = [r for r in fake_db.tables["sources"] if r["user_id"] == user_id][-1]
    return row


def _run(write, cap=2.0, confirm=True):
    from db.supabase_client import supabase
    from scripts.backfill_authorship import run
    return run(supabase, write=write, cap_usd=cap, confirm=lambda _: confirm)


def test_backfill_estimate_spends_nothing(fake_db, claude, capsys):
    _stored(fake_db, claude, OWN_NOTE)
    claude.calls.clear()
    claude.respond_with(lambda kw: pytest.fail("the estimate made a model call"))
    assert _run(write=False) == 0
    out = capsys.readouterr().out
    assert "to classify: 1 sources, 2 calls" in out and "Expected $" in out


def test_backfill_writes_skips_labelled_sources_and_lists_disagreements(fake_db, claude, capsys):
    own = _stored(fake_db, claude, OWN_NOTE, context="learning")
    mixed = _stored(fake_db, claude, MIXED, user_id=OTHER, context="work")
    ruled = _stored(fake_db, claude, "Our pricing is per seat. " * 10, user_id="user-rule")
    ruled["authorship"], ruled["authorship_set_by"] = "user_stated", "rule"

    calls = answer(claude, own_reading)
    assert _run(write=True) == 0
    out = capsys.readouterr().out
    assert len(calls) == 4                                       # two sources, two samples each
    assert "skipped: set by rule 1" in out
    assert own["authorship_set_by"] == "classifier" and mixed["authorship"] == "user_authored"
    assert "review (classifier differs from memory_context): 1" in out
    assert f"{own['source_id']} note memory_context=learning classifier=user_authored" in out
    assert ruled["authorship"] == "user_stated"

    calls = answer(claude, reading())
    _run(write=True)                                             # re-run: nothing left to read
    assert calls == []


def test_backfill_stops_at_the_spend_cap_and_asks_first(fake_db, claude, capsys):
    _stored(fake_db, claude, OWN_NOTE)
    _stored(fake_db, claude, MIXED, user_id=OTHER)
    calls = answer(claude, own_reading)
    assert _run(write=True, confirm=False) == 1
    assert calls == []
    _run(write=True, cap=0.000001)
    assert len(calls) == 2
    assert "left by the spend cap: 1" in capsys.readouterr().out


def test_backfill_never_overwrites_a_label_set_meanwhile(fake_db, claude):
    from memory.authorship_store import write_classifier_result
    row = _stored(fake_db, claude, OWN_NOTE)
    row["authorship"], row["authorship_set_by"] = "external", "user"
    assert write_classifier_result(dict(row, authorship_set_by=None), USER,
                                   authorship="user_authored", detail={"spans": []}) is False
    assert row["authorship"] == "external"


def test_paragraph_numbers_used_above_match_the_fixture():
    assert [MIXED[p.start:p.end].split()[0] for p in paragraphs(MIXED)] == ["own0", "quoted0", "my0"]
