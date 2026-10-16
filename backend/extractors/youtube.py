"""A YouTube video's transcript, through Supadata.

The preview (POST /fetch-youtube-transcript) fetches the transcript and keeps
Supadata's response here for CACHE_SECONDS, keyed by video id; saving the video
reads it from this cache, so one video costs one Supadata call. On a cache miss
(a restart, or a save that reaches another instance) the transcript is fetched
again. The source stores the video id, its canonical URL and Supadata's response.
"""
from __future__ import annotations

import os
import re
import threading
import time
from datetime import datetime, timezone

import httpx

from extractors import Extraction, ExtractionError, ServiceUnavailable
from memory.source_store import SourceOriginal

EXTRACTOR = ("supadata", "1")
CACHE_SECONDS = 30 * 60
_CACHE_MAX = 256
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()

_SHORT = re.compile(r"^https?://youtu\.be/([A-Za-z0-9_-]{11})")
_WATCH = re.compile(r"[?&]v=([A-Za-z0-9_-]{11})")
_SHORTS = re.compile(r"^https?://(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})")


def video_id(url: str) -> str | None:
    """The 11-character id in youtu.be/ID, youtube.com/watch?v=ID (any parameter
    order) or youtube.com/shorts/ID links."""
    url = url.strip()
    if m := _SHORT.match(url):
        return m.group(1)
    if "youtube.com" in url and (m := _WATCH.search(url)):
        return m.group(1)
    if m := _SHORTS.match(url):
        return m.group(1)
    return None


def canonical_url(vid: str) -> str:
    """The URL a video is stored and de-duplicated under."""
    return f"https://www.youtube.com/watch?v={vid}"


def _fetch(vid: str) -> dict:
    key = os.getenv("SUPADATA_API_KEY")
    if not key:
        raise ServiceUnavailable("Transcript service not configured")
    try:
        response = httpx.get("https://api.supadata.ai/v1/youtube/transcript",
                             params={"videoId": vid, "text": "true"}, headers={"x-api-key": key}, timeout=15)
    except httpx.RequestError:
        raise ServiceUnavailable("Transcript service error")
    if response.status_code == 404:
        raise ExtractionError("No transcript found for this video")
    if response.status_code == 429:
        raise ServiceUnavailable("Transcript service limit reached")
    if response.status_code != 200:
        raise ServiceUnavailable("Transcript service error")
    data = response.json()
    if not (data.get("content") or "").strip():
        raise ExtractionError("No transcript found for this video")
    return {**data, "fetched_at": datetime.now(timezone.utc).isoformat()}


def transcript(vid: str) -> dict:
    """Supadata's response for this video, from the cache when it is fresh."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(vid)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    data = _fetch(vid)
    with _lock:
        _cache[vid] = (now, data)
        for stale in [k for k, (t, _) in _cache.items() if now - t >= CACHE_SECONDS]:
            _cache.pop(stale, None)
        while len(_cache) > _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
    return data


def extract_video(url: str) -> Extraction:
    vid = video_id(url)
    if not vid:
        raise ExtractionError("Invalid YouTube URL. Supported formats: youtube.com/watch?v=ID, "
                              "youtu.be/ID, youtube.com/shorts/ID")
    data = transcript(vid)
    title = (data.get("title") or "").strip()
    stored = canonical_url(vid)
    raw = {k: v for k, v in data.items() if k != "fetched_at"}
    return Extraction(
        text=data["content"].strip(),
        title=title or f"YouTube video {vid}",
        original=SourceOriginal(
            input_type="youtube", extractor=EXTRACTOR[0], extractor_version=EXTRACTOR[1],
            raw_json={"video_id": vid, "response": raw}, raw_mime="application/json",
            source_url=stored, fetched_at=data["fetched_at"],
            title_origin="provided" if title else "derived",
        ),
        metadata={"video_id": vid},
    )
