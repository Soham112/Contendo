"""A YouTube video's transcript, through Supadata, and its title, through oEmbed.

Transcript. Supadata's /v1/transcript is asked for the existing transcript in
language.DEFAULT (mode=native: never the paid generate mode by default). Its
language is the text's own (utils/language.resolve, Supadata's `lang` only when
the text is too short to tell). When it isn't DEFAULT (a video with only an
auto-dubbed track, say), the transcript is generated once from the audio
(mode=generate, 2 credits a minute, in the language spoken), only for videos up
to AUDIO_MAX_MS long; the length is the native transcript's span. If that still
isn't DEFAULT, or the video is longer, the video is refused. The path each
video took is logged and stored in the source's raw_json.

Title. YouTube's oEmbed (free, no key) gives the title (title_origin
'provided') and the channel (the source's author). When it fails (a private or
age-restricted video) the title is "YouTube video <id>" ('derived').

The preview (POST /fetch-youtube-transcript) keeps the outcome here for
CACHE_SECONDS, keyed by video id, refusals included, so a save or a second
preview doesn't pay again. On a cache miss (a restart, another instance) the
video is fetched again.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import datetime, timezone

import httpx

from extractors import Extraction, ExtractionError, ServiceUnavailable
from memory.source_store import SourceOriginal
from utils import language

logger = logging.getLogger(__name__)

EXTRACTOR = ("supadata", "2")
API = "https://api.supadata.ai/v1"
OEMBED = "https://www.youtube.com/oembed"
AUDIO_MAX_MS = 60 * 60 * 1000
JOB_POLL_SECONDS = 1          # Supadata's recommended interval
JOB_TIMEOUT_SECONDS = 300
CACHE_SECONDS = 30 * 60
_CACHE_MAX = 256
_cache: dict[str, tuple[float, dict | ExtractionError]] = {}
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


def _no_transcript_message() -> str:
    return f"This video has no transcript in {language.name(language.DEFAULT)}."


def _checked(response: httpx.Response) -> dict:
    if response.status_code in (206, 404):
        raise ExtractionError("No transcript found for this video")
    if response.status_code == 429:
        raise ServiceUnavailable("Transcript service limit reached")
    if response.status_code not in (200, 202):
        raise ServiceUnavailable("Transcript service error")
    return response.json()


def _get(path: str, params: dict | None, key: str, timeout: float) -> dict:
    try:
        return _checked(httpx.get(f"{API}{path}", params=params, headers={"x-api-key": key}, timeout=timeout))
    except httpx.RequestError:
        raise ServiceUnavailable("Transcript service error")


def _wait_for_job(job_id: str, key: str) -> dict:
    """A 202's job, polled until it completes (generate mode may answer this way)."""
    deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(JOB_POLL_SECONDS)
        job = _get(f"/transcript/{job_id}", None, key, timeout=15)
        if job.get("status") == "completed":
            return job
        if job.get("status") == "failed":
            raise ExtractionError("Couldn't transcribe this video's audio")
    raise ServiceUnavailable("Transcript service is taking too long")


def _transcript(vid: str, mode: str, key: str) -> dict:
    """One Supadata transcript: its text, reported language, span and raw response."""
    params = {"url": canonical_url(vid), "mode": mode, "text": "false"}
    if mode == "native":
        params["lang"] = language.DEFAULT   # generate ignores lang: it transcribes the spoken language
    data = _get("/transcript", params, key, timeout=15 if mode == "native" else 120)
    if "jobId" in data and "content" not in data:
        data = _wait_for_job(data["jobId"], key)
    content = data.get("content") or []
    if isinstance(content, str):
        text, span_ms = content, None
    else:
        text = " ".join(c["text"].strip() for c in content if (c.get("text") or "").strip())
        span_ms = max((c.get("offset", 0) + c.get("duration", 0) for c in content), default=None)
    if not text.strip():
        raise ExtractionError("No transcript found for this video")
    lang = language.resolve(text, data.get("lang"))
    return {"text": text.strip(), "lang": lang, "reported_lang": data.get("lang"),
            "span_ms": span_ms, "response": {k: v for k, v in data.items() if k != "jobId"}}


def _oembed(vid: str) -> dict | None:
    """{title, author_name} from YouTube oEmbed, or None when it fails."""
    try:
        response = httpx.get(OEMBED, params={"url": canonical_url(vid), "format": "json"}, timeout=5)
        data = response.json() if response.status_code == 200 else None
    except (httpx.RequestError, ValueError):
        return None
    if not isinstance(data, dict) or not (data.get("title") or "").strip():
        return None
    return {"title": data["title"].strip(), "author_name": (data.get("author_name") or "").strip() or None}


def _fetch(vid: str) -> dict:
    key = os.getenv("SUPADATA_API_KEY")
    if not key:
        raise ServiceUnavailable("Transcript service not configured")
    wanted = (language.DEFAULT, None)   # None: too short to tell and no reported language
    native, audio = _transcript(vid, "native", key), None
    if native["lang"] in wanted:
        accepted, path = native, "native"
    elif native["span_ms"] is None or native["span_ms"] > AUDIO_MAX_MS:
        accepted, path = None, "refused_too_long_for_audio"
    else:
        audio = _transcript(vid, "generate", key)
        accepted, path = (audio, "audio") if audio["lang"] in wanted else (None, "refused_after_audio")
    logger.info("youtube %s: path=%s native_lang=%s reported=%s span_ms=%s audio_lang=%s",
                vid, path, native["lang"], native["reported_lang"], native["span_ms"],
                audio and audio["lang"])
    if accepted is None:
        raise ExtractionError(_no_transcript_message())
    return {
        "text": accepted["text"], "lang": accepted["lang"], "path": path,
        "native": {k: native[k] for k in ("lang", "reported_lang", "span_ms")},
        "response": accepted["response"], "oembed": _oembed(vid),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def transcript(vid: str) -> dict:
    """The video's outcome, from the cache when it is fresh. A refusal is cached
    and raised again; a service failure is not cached."""
    now = time.monotonic()
    with _lock:
        hit = _cache.get(vid)
    if hit and now - hit[0] < CACHE_SECONDS:
        if isinstance(hit[1], ExtractionError):
            raise ExtractionError(str(hit[1]))
        return hit[1]
    try:
        outcome: dict | ExtractionError = _fetch(vid)
    except ServiceUnavailable:
        raise
    except ExtractionError as e:
        outcome = e
    with _lock:
        _cache[vid] = (now, outcome)
        for stale in [k for k, (t, _) in _cache.items() if now - t >= CACHE_SECONDS]:
            _cache.pop(stale, None)
        while len(_cache) > _CACHE_MAX:
            _cache.pop(next(iter(_cache)))
    if isinstance(outcome, ExtractionError):
        raise outcome
    return outcome


def extract_video(url: str) -> Extraction:
    vid = video_id(url)
    if not vid:
        raise ExtractionError("Invalid YouTube URL. Supported formats: youtube.com/watch?v=ID, "
                              "youtu.be/ID, youtube.com/shorts/ID")
    data = transcript(vid)
    oembed = data["oembed"] or {}
    raw = {k: data[k] for k in ("path", "native", "response", "oembed")}
    return Extraction(
        text=data["text"],
        title=oembed.get("title") or f"YouTube video {vid}",
        original=SourceOriginal(
            input_type="youtube", extractor=EXTRACTOR[0], extractor_version=EXTRACTOR[1],
            raw_json={"video_id": vid, **raw}, raw_mime="application/json",
            source_url=canonical_url(vid), fetched_at=data["fetched_at"],
            title_origin="provided" if oembed.get("title") else "derived",
            author=oembed.get("author_name"),
        ),
        metadata={"video_id": vid, "lang": data["lang"]},
    )
