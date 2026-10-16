"""YouTube extraction (backend/extractors/youtube.py): the title from oEmbed, the
transcript in English with the audio fallback, and the cache, against Supadata
and oEmbed responses saved in tests/fixtures/extraction (see each file's _note)."""
import httpx
import pytest

from extractors import ExtractionError
from tests.extraction_fixtures import jina as fixture

USER = "user-a"
VID = "o0UmCtfL1UY"
URL = f"https://youtu.be/{VID}"
NO_ENGLISH = "This video has no transcript in English."


@pytest.fixture
def ingestion(claude):
    claude.respond_with(lambda kwargs: "[]")


@pytest.fixture
def headers(client, production, auth_headers):
    return auth_headers(USER)


@pytest.fixture(autouse=True)
def _empty_transcript_cache():
    from extractors import youtube
    youtube._cache.clear()
    yield
    youtube._cache.clear()


def _saved(name: str) -> dict:
    return {k: v for k, v in fixture(name).items() if k != "_note"}


class FakeServices:
    """httpx.get for Supadata and oEmbed: records each call as its mode ("native",
    "generate"), "job" or "oembed"."""

    def __init__(self, native: str, generate: str | None = None, oembed: int | Exception = 200,
                 generate_as_job: bool = False):
        self.native, self.generate, self.oembed, self.as_job = native, generate, oembed, generate_as_job
        self.calls: list[str] = []
        self.params: list[dict] = []

    def __call__(self, url, params=None, **kw):
        from extractors import youtube
        if url == youtube.OEMBED:
            self.calls.append("oembed")
            if isinstance(self.oembed, Exception):
                raise self.oembed
            body = fixture("oembed_o0UmCtfL1UY.json") if self.oembed == 200 else None
            return httpx.Response(self.oembed, json=body) if body else httpx.Response(self.oembed, text="Unauthorized")
        if url.endswith("/transcript"):
            self.calls.append(params["mode"])
            self.params.append(params)
            if params["mode"] == "native":
                return httpx.Response(200, json=_saved(self.native))
            if self.as_job:
                return httpx.Response(202, json={"jobId": "job-1"})
            return httpx.Response(200, json=_saved(self.generate))
        assert url.endswith("/transcript/job-1"), url
        self.calls.append("job")
        return httpx.Response(200, json={"status": "completed", **_saved(self.generate)})


@pytest.fixture
def services(monkeypatch):
    from extractors import youtube
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")
    monkeypatch.setattr(youtube.time, "sleep", lambda s: None)

    def use(**kw) -> FakeServices:
        fake = FakeServices(**kw)
        monkeypatch.setattr(youtube.httpx, "get", fake)
        return fake
    return use


@pytest.mark.parametrize("url", ["https://youtu.be/abcdefghijk", "https://www.youtube.com/watch?t=3&v=abcdefghijk",
                                 "https://youtube.com/shorts/abcdefghijk"])
def test_video_ids(url):
    from extractors.youtube import video_id
    assert video_id(url) == "abcdefghijk"


def test_english_transcript_is_used_with_the_oembed_title_and_one_call(client, headers, fake_db, ingestion,
                                                                       services):
    fake = services(native="supadata_native_en.json")
    preview = client.post("/fetch-youtube-transcript", headers=headers, json={"url": URL})
    assert preview.status_code == 200
    assert preview.json()["title"] == "How to Build a Custom Shopify Store using AI (Claude Code)"
    saved = client.post("/ingest", headers=headers, json={"source_type": "youtube", "video_url": URL})
    assert saved.status_code == 200 and saved.json()["chunks_stored"] > 0

    assert fake.calls == ["native", "oembed"]                      # the save read the cache
    assert fake.params[0] == {"url": f"https://www.youtube.com/watch?v={VID}", "mode": "native",
                            "text": "false", "lang": "en"}
    [row] = fake_db.tables["sources"]
    assert (row["extractor"], row["extractor_version"]) == ("supadata", "2")
    assert (row["title_origin"], row["author"], row["lang"]) == ("provided", "Kyle Skelly", "en")
    assert row["raw_json"]["path"] == "native" and row["raw_json"]["oembed"]["author_name"] == "Kyle Skelly"
    assert row["extracted_text"].startswith("In today's video, I'm going to show you guys how to build")


@pytest.mark.parametrize("as_job", [False, True])
def test_a_dubbed_track_is_replaced_by_the_audio_transcript(client, headers, fake_db, ingestion, services, as_job):
    fake = services(native="supadata_native_ar_dub.json", generate="supadata_generate_en.json",
                    generate_as_job=as_job)
    saved = client.post("/ingest", headers=headers, json={"source_type": "youtube", "video_url": URL})
    assert saved.status_code == 200
    assert fake.calls == ["native", "generate"] + (["job"] if as_job else []) + ["oembed"]
    assert "lang" not in fake.params[1]                           # generate transcribes the spoken language
    [row] = fake_db.tables["sources"]
    assert row["lang"] == "en" and row["raw_json"]["path"] == "audio"
    assert row["raw_json"]["native"]["lang"] == "ar"
    assert row["extracted_text"].startswith("In today's video")


def test_a_track_labelled_english_but_not_english_is_refused_after_the_audio_try(client, headers, fake_db,
                                                                                 services):
    """The real Despacito case: Supadata reported 'en' for Spanish lyrics."""
    fake = services(native="supadata_native_es_labelled_en.json", generate="supadata_generate_es.json")
    for _ in range(2):
        resp = client.post("/fetch-youtube-transcript", headers=headers, json={"url": URL})
        assert resp.status_code == 422 and resp.json()["detail"] == NO_ENGLISH
    assert fake.calls == ["native", "generate"]                   # the refusal is cached: no second payment
    assert fake_db.tables["sources"] == []


def test_a_video_over_an_hour_skips_the_audio_fallback(client, headers, fake_db, services):
    fake = services(native="supadata_native_ar_long.json", generate="supadata_generate_en.json")
    resp = client.post("/ingest", headers=headers, json={"source_type": "youtube", "video_url": URL})
    assert resp.status_code == 422 and resp.json()["detail"] == NO_ENGLISH
    assert fake.calls == ["native"]


@pytest.mark.parametrize("limit, calls", [(486_360, ["native", "generate", "oembed"]), (486_359, ["native"])])
def test_the_length_limit_is_the_transcript_span(services, monkeypatch, limit, calls):
    from extractors import youtube
    monkeypatch.setattr(youtube, "AUDIO_MAX_MS", limit)          # the dub fixture spans 486,360 ms
    fake = services(native="supadata_native_ar_dub.json", generate="supadata_generate_en.json")
    try:
        youtube.extract_video(URL)
    except ExtractionError as e:
        assert str(e) == NO_ENGLISH
    assert fake.calls == calls


@pytest.mark.parametrize("oembed", [401, 404, httpx.ConnectError("down")])
def test_without_oembed_the_title_is_derived_from_the_id(services, oembed):
    from extractors import youtube
    services(native="supadata_native_en.json", oembed=oembed)
    e = youtube.extract_video(URL)
    assert e.title == f"YouTube video {VID}"
    assert (e.original.title_origin, e.original.author) == ("derived", None)
    assert e.text.startswith("In today's video")


def test_a_stale_or_missing_cache_entry_fetches_again(services, monkeypatch):
    from extractors import youtube
    fake = services(native="supadata_native_en.json")
    clock = [1000.0]
    monkeypatch.setattr(youtube.time, "monotonic", lambda: clock[0])
    youtube.transcript(VID)
    youtube.transcript(VID)
    clock[0] += youtube.CACHE_SECONDS + 1
    youtube.transcript(VID)
    youtube._cache.clear()                                       # a restart
    youtube.transcript(VID)
    assert fake.calls.count("native") == 3


def test_a_service_failure_is_not_cached(services, monkeypatch):
    from extractors import ServiceUnavailable, youtube
    services(native="supadata_native_en.json")
    monkeypatch.setattr(youtube.httpx, "get", lambda *a, **k: httpx.Response(429, json={}))
    with pytest.raises(ServiceUnavailable):
        youtube.transcript(VID)
    services(native="supadata_native_en.json")
    assert youtube.transcript(VID)["path"] == "native"
