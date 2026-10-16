"""Extraction (backend/extractors/): each input type against saved or generated
inputs, the duplicate check and replace on the routes, and how today's chunker
and BM25 treat the structured text the extractors now produce."""
import base64

import pytest

from extractors import ExtractionError, ServiceUnavailable
from tests.extraction_fixtures import encrypted, jina, make_docx, make_pdf, report_pdf

USER = "user-a"


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


# --- URL ------------------------------------------------------------------------------

def test_page_text_is_the_main_content_with_the_real_title():
    from extractors.url import extract
    e = extract("https://EN.wikipedia.org/wiki/Retrieval-augmented_generation#History",
                jina("jina_wikipedia_rag.json"), "2026-10-16T00:00:00+00:00")
    assert e.title == "Retrieval-augmented generation" and e.original.title_origin == "provided"
    assert e.original.source_url == "https://en.wikipedia.org/wiki/Retrieval-augmented_generation"
    for leaked in ("URL Source:", "Markdown Content:", "Jump to content", "](", "http"):
        assert leaked not in e.text
    assert e.text.startswith("From Wikipedia") and "is a technique that enables" in e.text
    assert e.original.raw_json["data"]["httpStatus"] == 200        # Jina reports the target's status


def test_a_page_the_site_answers_with_an_error_is_refused():
    from extractors.url import extract
    with pytest.raises(ExtractionError, match="404"):
        extract("https://en.wikipedia.org/wiki/x", jina("jina_wikipedia_404.json"), "t")


def test_too_little_main_content_is_refused():
    from extractors.url import extract
    body = {"code": 200, "data": {"title": "Just a moment", "content": "Verifying you are human.", "httpStatus": 200}}
    with pytest.raises(ExtractionError, match="enough article text"):
        extract("https://e.com/a", body, "t")


def test_short_lines_and_lists_are_kept():
    from extractors.url import extract
    content = "# Steps\n\n" + "Intro sentence about the process here. " * 12 + "\n\n- Plan\n- Ship\n\nStep 3\n\nDone."
    e = extract("https://e.com/a", {"data": {"title": "Steps", "content": content, "httpStatus": 200}}, "t")
    for kept in ("# Steps", "- Plan", "- Ship", "Step 3", "Done."):
        assert kept in e.text


def test_reader_rate_limit_is_a_service_problem(monkeypatch):
    import httpx
    from extractors import url
    monkeypatch.setattr(url.httpx, "get", lambda *a, **k: httpx.Response(429, json={}))
    with pytest.raises(ServiceUnavailable):
        url.fetch("https://e.com/a")


@pytest.mark.parametrize("given,stored", [
    ("https://Example.COM/Path/?b=2&a=1#frag", "https://example.com/Path/?b=2&a=1"),
    ("HTTP://example.com:80/a", "http://example.com/a"),
    ("https://example.com:8443/a", "https://example.com:8443/a"),
    ("https://example.com/a/", "https://example.com/a/"),      # trailing slash kept: may be another page
])
def test_url_normalisation_is_conservative(given, stored):
    from extractors.url import normalize_url
    assert normalize_url(given) == stored


# --- files ----------------------------------------------------------------------------

def test_pdf_drops_running_headers_and_page_numbers_and_rebuilds_paragraphs():
    from extractors.file import extract_pdf
    text = extract_pdf(report_pdf())
    assert "Acme Quarterly Report" not in text and "Page 2 of 4" not in text
    assert "talks about deployment of the pipeline" in text          # hyphenated across a line break
    assert "Paragraph one of page 1 talks about section1 the next line of paragraph one." in text
    assert "\n\nParagraph two of page 1" in text


def test_a_line_repeated_in_the_body_is_content_not_a_header():
    from extractors.file import extract_pdf
    pages = [[(700, "Remember: measure before you change anything at all."), (650, f"Body text for page {p}.")]
             for p in range(4)]
    assert extract_pdf(make_pdf(pages)).count("Remember: measure") == 4


def test_short_documents_keep_their_header_lines():
    """Fewer than 3 pages: nothing counts as running, so nothing is removed."""
    from extractors.file import extract_pdf
    text = extract_pdf(report_pdf(n_pages=2))
    assert text.count("Acme Quarterly Report") == 2


@pytest.mark.parametrize("pdf,message", [
    (lambda: make_pdf([[(700, "Scan")]]), "This PDF is a scanned image. Upload a text PDF or a photo of the page instead."),
    (lambda: encrypted(report_pdf()), "password-protected"),
    (lambda: b"%PDF-1.4 garbage", "Could not open this PDF"),
])
def test_unreadable_pdfs_say_why(pdf, message):
    from extractors.file import extract_pdf
    with pytest.raises(ExtractionError, match=message):
        extract_pdf(pdf())


def test_docx_keeps_headings_tables_and_short_lines_in_order():
    from extractors.file import extract_docx
    assert extract_docx(make_docx()) == (
        "# Launch plan\n\n## Goals\n\nShip the importer by May.\n\nOwner | Due\nPriya | May 3\n\nOk.")


def test_markdown_and_text_files_and_the_filename_title():
    from extractors.file import extract_file
    md = extract_file("Pricing notes.md", b"# Pricing\n\nSee [the post](https://x.com/p) ![chart](c.png) now.", None)
    assert md.text == "# Pricing\n\nSee the post  now." and md.title == "Pricing notes"
    assert (md.original.title_origin, md.original.extractor, md.original.extractor_version) == \
        ("provided", "file_extractor.md", "2")
    assert extract_file("a.txt", b"  plain [not a link]  ", "text/plain").text == "plain [not a link]"
    with pytest.raises(ExtractionError, match="Unsupported"):
        extract_file("a.pptx", b"x", None)


# --- Obsidian ---------------------------------------------------------------------------

def test_obsidian_fixes_embeds_math_and_aliases():
    from extractors.obsidian import clean_obsidian_markdown
    note = ("---\ntags: [x]\n---\n# Growth\n\n![[chart.png]]\nSee [[Pricing|our pricing page]] and [[Churn#Q3]].\n"
            "Area grows as x^2 when ==both== sides double. ^block-1\n```dataview\nLIST\n```\nEnd.")
    assert clean_obsidian_markdown(note) == (
        "# Growth\n\nSee our pricing page and Churn.\nArea grows as x^2 when both sides double.\n\nEnd.")


# --- YouTube ----------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["https://youtu.be/abcdefghijk", "https://www.youtube.com/watch?t=3&v=abcdefghijk",
                                 "https://youtube.com/shorts/abcdefghijk"])
def test_video_ids(url):
    from extractors.youtube import video_id
    assert video_id(url) == "abcdefghijk"


@pytest.fixture
def supadata(monkeypatch):
    import httpx
    from extractors import youtube
    calls = []

    def get(url, **kw):
        calls.append(kw["params"]["videoId"])
        return httpx.Response(200, json={"content": "Today we talk about pricing. " * 30, "title": "Pricing talk"})
    monkeypatch.setenv("SUPADATA_API_KEY", "test-key")
    monkeypatch.setattr(youtube.httpx, "get", get)
    return calls


def test_preview_then_save_costs_one_transcript_call(client, headers, fake_db, ingestion, supadata):
    url = "https://youtu.be/abcdefghijk"
    preview = client.post("/fetch-youtube-transcript", headers=headers, json={"url": url})
    assert preview.status_code == 200 and preview.json()["title"] == "Pricing talk"
    saved = client.post("/ingest", headers=headers, json={"source_type": "youtube", "video_url": url})
    assert saved.status_code == 200 and saved.json()["chunks_stored"] > 0
    assert supadata == ["abcdefghijk"]
    [row] = fake_db.tables["sources"]
    assert (row["extractor"], row["source_url"]) == ("supadata", "https://www.youtube.com/watch?v=abcdefghijk")
    assert row["raw_json"]["video_id"] == "abcdefghijk" and row["raw_json"]["response"]["title"] == "Pricing talk"


def test_a_stale_or_missing_cache_entry_fetches_again(supadata, monkeypatch):
    from extractors import youtube
    clock = [1000.0]
    monkeypatch.setattr(youtube.time, "monotonic", lambda: clock[0])
    youtube.transcript("abcdefghijk")
    youtube.transcript("abcdefghijk")
    clock[0] += youtube.CACHE_SECONDS + 1
    youtube.transcript("abcdefghijk")
    youtube._cache.clear()                                   # a restart
    youtube.transcript("abcdefghijk")
    assert supadata == ["abcdefghijk"] * 3


# --- images -----------------------------------------------------------------------------

def _reading(monkeypatch, text, description):
    import extractors.image as image
    from agents.vision_agent import ImageReading
    monkeypatch.setattr(image, "read_image", lambda *a, **k: ImageReading(transcribed_text=text,
                                                                          description=description))


def test_image_text_and_description_are_kept_apart(monkeypatch):
    from extractors.image import extract_image
    _reading(monkeypatch, "Q3 goals\n- ship importer", "A whiteboard photo with a list.")
    e = extract_image(b"img", "aW1n", "image/png", user_id=USER)
    assert e.text == ("# Text in the image\n\nQ3 goals\n- ship importer\n\n"
                      "# What the image shows\n\nA whiteboard photo with a list.")
    assert e.title == "Q3 goals" and e.original.extractor_version == "2"


def test_image_without_text_uses_the_description(monkeypatch):
    from extractors.image import extract_image
    _reading(monkeypatch, "", "A dog on a beach.")
    e = extract_image(b"img", "aW1n", "image/png", user_id=USER)
    assert e.text == "# What the image shows\n\nA dog on a beach." and e.title == "A dog on a beach."
    _reading(monkeypatch, " ", "")
    with pytest.raises(ExtractionError):
        extract_image(b"img", "aW1n", "image/png", user_id=USER)


def test_vision_call_returns_both_parts(claude):
    from agents.vision_agent import read_image
    claude.queue('{"transcribed_text": "Agenda", "description": "A slide."}')
    reading = read_image("data:image/png;base64,AAAA", media_type="image/png", user_id=USER)
    assert (reading.transcribed_text, reading.description) == ("Agenda", "A slide.")
    assert claude.calls[0]["model"] == "claude-sonnet-4-6"


# --- duplicates and replace --------------------------------------------------------------

def _upload(client, headers, data, name="plan.txt", **form):
    return client.post("/ingest-file", headers=headers, files={"file": (name, data, "text/plain")}, data=form)


NOTE = "Notes from rebuilding our billing pipeline in the spring. " * 20


def test_same_file_again_is_a_replaceable_duplicate_found_before_extraction(client, headers, fake_db, ingestion,
                                                                            claude, monkeypatch):
    first = _upload(client, headers, NOTE.encode())
    assert first.status_code == 200
    calls = len(claude.calls)
    import routers.ingest as routes
    monkeypatch.setattr(routes, "extract_file", lambda *a: pytest.fail("extracted a known file"))

    again = _upload(client, headers, NOTE.encode(), name="renamed.txt").json()
    [row] = fake_db.tables["sources"]
    assert again["duplicate"] and again["replaceable"] and again["existing_source_id"] == row["source_id"]
    assert len(claude.calls) == calls


def test_replace_re_extracts_into_the_same_source(client, headers, fake_db, ingestion, monkeypatch):
    _upload(client, headers, NOTE.encode())
    [row] = fake_db.tables["sources"]
    old_chunks = {r["id"] for r in fake_db.tables["embeddings"]}
    import routers.ingest as routes
    from extractors.file import extract_file
    monkeypatch.setattr(routes, "extract_file",       # a newer extractor gives different text for the same bytes
                        lambda name, data, mime: extract_file(name, (NOTE + " Improved.").encode(), mime))

    resp = _upload(client, headers, NOTE.encode(), replace_source_id=row["source_id"])
    assert resp.status_code == 200 and not resp.json()["duplicate"]
    [after] = fake_db.tables["sources"]
    assert after["source_id"] == row["source_id"] and after["extracted_text"].endswith("Improved.")
    assert not old_chunks & {r["id"] for r in fake_db.tables["embeddings"]}


def test_replace_only_targets_the_source_with_the_same_file(client, headers, fake_db, ingestion):
    _upload(client, headers, NOTE.encode())
    [row] = fake_db.tables["sources"]
    resp = _upload(client, headers, b"A different file entirely. " * 20, replace_source_id=row["source_id"])
    assert resp.status_code == 409
    assert len(fake_db.tables["sources"]) == 1


def test_same_url_is_a_duplicate_found_before_fetching(client, headers, fake_db, ingestion, monkeypatch):
    import extractors.url as url_extractor
    fetched = []
    monkeypatch.setattr(url_extractor, "fetch", lambda url: fetched.append(url) or jina("jina_wikipedia_rag.json"))
    assert client.post("/scrape-and-ingest", headers=headers, json={"url": "https://en.wikipedia.org/wiki/R"}).status_code == 200
    again = client.post("/scrape-and-ingest", headers=headers, json={"url": "https://EN.wikipedia.org/wiki/R#x"}).json()
    assert again["duplicate"] and again["replaceable"] and len(fetched) == 1


def test_same_image_is_a_duplicate_found_before_the_vision_call(client, headers, fake_db, ingestion, monkeypatch):
    _reading(monkeypatch, "Q3 goals " * 10, "")
    image = "data:image/png;base64," + base64.b64encode(b"\x89PNG same bytes").decode()
    assert client.post("/ingest", headers=headers, json={"source_type": "image", "raw_image": image}).status_code == 200
    import extractors.image as image_extractor
    monkeypatch.setattr(image_extractor, "read_image", lambda *a, **k: pytest.fail("read a known image"))
    again = client.post("/ingest", headers=headers, json={"source_type": "image", "raw_image": image}).json()
    assert again["duplicate"] and again["replaceable"]


def test_same_text_from_new_bytes_is_a_duplicate_replace_would_not_change(client, headers, fake_db, ingestion):
    _upload(client, headers, NOTE.encode())
    again = _upload(client, headers, NOTE.encode() + b"\n\n").json()   # new bytes, same text after stripping
    assert again["duplicate"] and not again["replaceable"]
    assert again["existing_source_id"] == fake_db.tables["sources"][0]["source_id"]


# --- the current chunker and BM25 with structured text (until step 3.4) -------------------

def test_structured_text_loses_nothing_in_todays_chunker_and_bm25():
    """Markup tokens (#, |) count as words in the 500-word chunker, so chunk
    boundaries move by a few words; BM25 ignores them and no real word is
    dropped. Step 3.4 replaces the chunker."""
    from memory.vector_store import _tokenize
    from utils.chunker import chunk_text
    body = " ".join(f"word{i}" for i in range(1200))
    structured = f"# Launch plan\n\n## Goals\n\n{body}\n\nOwner | Due\nPriya | May 3"
    plain = f"Launch plan Goals {body} Owner Due Priya May 3"

    s_chunks, p_chunks = chunk_text(structured), chunk_text(plain)
    assert len(s_chunks) == len(p_chunks) == 3
    covered = {t for c in s_chunks for t in _tokenize(c)}
    assert covered == {t for c in p_chunks for t in _tokenize(c)}          # every real word is in a chunk
    markup = [w for c in s_chunks for w in c.split()
              if w not in {x for p in p_chunks for x in p.split()}]
    assert set(markup) == {"#", "##", "|"}                                 # the only extra "words"
    assert _tokenize(structured) == _tokenize(plain)                       # BM25 sees the same terms
