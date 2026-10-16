"""Extraction: one module per input type, each turning what the user gave us
into the text that is chunked, plus its title and its original.

    url.py       a web page, through Jina Reader's JSON mode
    file.py      an uploaded PDF, DOCX, TXT or Markdown file
    youtube.py   a video's transcript, through Supadata (cached between preview and save)
    image.py     an image, through the vision call in agents/vision_agent.py
    obsidian.py  an Obsidian note

Typed notes are stored as received (memory.source_store.typed_text) and the
business notes are built by utils.business_notes: neither has an extraction step.

Output contract, the same for every extractor: plain text that keeps the
document's structure, so chunking can use it (step 3.4): headings as `#` lines,
paragraphs separated by a blank line, list items, table rows as `a | b`. Markup
and metadata are removed by syntax and layout, never by word lists, and no line
is dropped because it is short.

Every extractor has a (name, version) pair, recorded on the source. Bump the
version whenever an extractor's output changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memory.source_store import SourceOriginal


class ExtractionError(ValueError):
    """The input can't be extracted. The message is shown to the user as is."""


class ServiceUnavailable(ExtractionError):
    """The outside service (reader, transcripts) is unconfigured, rate-limited or
    failing: the input may be fine, try again later."""


@dataclass(frozen=True)
class Extraction:
    text: str
    title: str
    original: SourceOriginal
    metadata: dict[str, Any] = field(default_factory=dict)
