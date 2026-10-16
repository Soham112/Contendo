"""A web page, through Jina Reader's JSON mode (r.jina.ai, anonymous tier: 20
requests a minute).

JSON mode returns the page's title, its main content (no navigation; on the
Wikipedia fixture 2,384 words against 7,480 in markdown mode), its published
time and the target site's own HTTP status. A page is refused on structure
only: Jina's own error, a non-2xx target status (a site's 404 page comes back
as a 200 from Jina, with httpStatus 404), or too little main content. No
phrase lists.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import httpx

from extractors import Extraction, ExtractionError, ServiceUnavailable
from extractors.markdown import normalize_markdown
from memory.source_store import fetched_page

EXTRACTOR = ("jina_reader", "2")   # 2: JSON mode, title field, structural checks, no line filter
MIN_WORDS = 50                     # less main content than this is not an article
_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(url: str) -> str:
    """The URL a source is stored and de-duplicated under. Conservative, so two
    different pages are never merged: lowercase scheme and host, no fragment,
    no default port. Path, query and trailing slash are kept as given."""
    parts = urlsplit(url.strip())
    scheme, host = parts.scheme.lower(), (parts.hostname or "").lower()
    netloc = host if parts.port in (None, _DEFAULT_PORTS.get(scheme)) else f"{host}:{parts.port}"
    if parts.username:
        netloc = f"{parts.username}@{netloc}"
    return urlunsplit((scheme, netloc, parts.path, parts.query, ""))


def is_valid_url(url: str) -> bool:
    parts = urlsplit(url.strip())
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def fetch(url: str) -> dict:
    """Jina's JSON response for this URL. Raises ExtractionError on failure."""
    try:
        response = httpx.get(
            f"https://r.jina.ai/{url}",
            headers={"Accept": "application/json", "X-Retain-Images": "none"},
            timeout=30.0, follow_redirects=True,
        )
    except httpx.TimeoutException:
        raise ExtractionError("The request timed out. The site may be slow or blocking readers. "
                              "Try copying the text instead.")
    except httpx.RequestError:
        raise ExtractionError("Could not reach the URL. Check the link and try again.")
    if response.status_code == 429:
        raise ServiceUnavailable("Too many links in a short time. Wait a minute and try again.")
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code != 200 or not isinstance(body.get("data"), dict):
        raise ExtractionError("This page could not be read (it may block automated access). "
                              "Try copying the text instead.")
    return body


def extract(url: str, body: dict, fetched_at: str) -> Extraction:
    """The page in a Jina JSON response (from fetch, or a saved fixture)."""
    data = body["data"]
    status = data.get("httpStatus")
    if isinstance(status, int) and not 200 <= status < 300:
        raise ExtractionError(f"The page returned an error ({status} {data.get('httpStatusText') or ''})."
                              .replace(" )", ")") + " Check the link.")
    text = normalize_markdown(data.get("content") or "")
    if len(text.split()) < MIN_WORDS:
        raise ExtractionError("Could not find enough article text on this page. It may need a login, be "
                              "paywalled, or be a bot check. Try copying the text instead.")
    title = (data.get("title") or "").strip()
    stored_url = normalize_url(url)
    return Extraction(
        text=text,
        title=title or stored_url,
        original=fetched_page(url=stored_url, response_json=body, fetched_at=fetched_at,
                              extractor=EXTRACTOR, title_provided=bool(title)),
        metadata={"published_time": data.get("publishedTime"), "word_count": len(text.split())},
    )


def extract_url(url: str) -> Extraction:
    if not is_valid_url(url):
        raise ExtractionError("Invalid URL. Please include https:// at the start.")
    body = fetch(url.strip())
    return extract(url, body, datetime.now(timezone.utc).isoformat())
