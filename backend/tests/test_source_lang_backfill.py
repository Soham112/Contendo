"""Source language report and `sources.lang` backfill (scripts/backfill_source_lang.py)."""
from scripts import backfill_source_lang as backfill
from tests.test_language import ENGLISH, SPANISH

USER_A = "aaaaaaaa-1111-2222-3333-444444444444"
USER_B = "bbbbbbbb-1111-2222-3333-444444444444"


def _source(source_id: str, user_id: str, text: str, input_type: str = "url", lang=None) -> dict:
    return {"source_id": source_id, "user_id": user_id, "input_type": input_type,
            "extracted_text": text, "title": "Private title", "lang": lang}


def _seed(fake_db, rows):
    fake_db.tables["sources"] = rows


def test_report_counts_languages_per_user_and_flags_non_english_by_id_only(fake_db, capsys):
    _seed(fake_db, [_source("s-en-0001", USER_A, ENGLISH), _source("s-es-0002", USER_A, SPANISH, "youtube"),
                    _source("s-short-03", USER_B, "Meeting w/ Raj re pricing")])
    backfill.run(fake_db, write=False)
    out = capsys.readouterr().out
    assert "sources read: 3" in out
    assert "by language: en 1, es 1, undetermined 1" in out
    assert "  aaaaaaaa: en 1, es 1" in out and "  bbbbbbbb: undetermined 1" in out
    assert "not in a supported language: 1" in out and "  aaaaaaaa s-es-000 youtube es" in out
    assert USER_A not in out                                   # truncated ids only
    assert "Private title" not in out and "semana" not in out and "signup" not in out
    assert all(r["lang"] is None for r in fake_db.tables["sources"])   # report only: no writes


def test_apply_sets_determined_languages_and_leaves_undetermined_and_existing_alone(fake_db, capsys):
    _seed(fake_db, [_source("s1", USER_A, ENGLISH), _source("s2", USER_A, SPANISH),
                    _source("s3", USER_B, "short note"), _source("s4", USER_B, ENGLISH, lang="en")])
    backfill.run(fake_db, write=True)
    assert {r["source_id"]: r["lang"] for r in fake_db.tables["sources"]} == {
        "s1": "en", "s2": "es", "s3": None, "s4": "en"}
    assert "set lang on 2 sources" in capsys.readouterr().out
    backfill.run(fake_db, write=True)                         # re-running changes nothing
    assert "set lang on 0 sources" in capsys.readouterr().out


def test_every_page_is_read(fake_db, monkeypatch):
    monkeypatch.setattr(backfill, "PAGE", 2)
    _seed(fake_db, [_source(f"s{i}", USER_A, ENGLISH) for i in range(5)])
    assert len(backfill.fetch_sources(fake_db, with_lang=False)) == 5


def test_production_apply_needs_confirmation():
    import pytest
    with pytest.raises(SystemExit):
        backfill.main(["--apply"])
