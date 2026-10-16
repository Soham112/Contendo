"""Rebuild a source's text from its stored chunks (sources stored before
originals were kept). Pure: no database access.

chunker_v1 (utils.chunker) splits on whitespace into 500-word windows that
overlap by 50 words. So the text is chunk 0's words followed by every later
chunk's words after the first 50. The rebuild is verified by chunking the
result again with the same chunker and comparing with the stored chunks; the
original line breaks and spacing cannot be recovered.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from utils.chunker import OVERLAP_WORDS, _join, _tokenize, chunk_text

CHUNKER_VERSION = "chunker_v1"


@dataclass(frozen=True)
class Rebuild:
    text: str
    check: str               # rechunk_exact | rechunk_mismatch | incomplete
    hash_match: bool | None  # None when there is no stored hash to compare


def _content_hash(text: str) -> str:
    # Same normalisation as ingestion_agent.compute_content_hash.
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def _complete(chunks: list[dict]) -> bool:
    """Indexes 0..total_chunks-1 each exactly once, and every row agrees on total_chunks."""
    totals = {c.get("total_chunks") for c in chunks}
    indexes = sorted(c.get("chunk_index") for c in chunks)
    if len(totals) != 1 or None in totals:
        return False
    return indexes == list(range(totals.pop()))


def rebuild_source(chunks: list[dict]) -> Rebuild:
    """chunks: one source's rows with content, chunk_index, total_chunks, content_hash."""
    ordered = sorted(chunks, key=lambda c: c.get("chunk_index") or 0)
    words: list[str] = []
    for i, chunk in enumerate(ordered):
        tokens = _tokenize(chunk.get("content") or "")
        words.extend(tokens if i == 0 else tokens[OVERLAP_WORDS:])
    text = _join(words)

    stored_hashes = {c.get("content_hash") for c in ordered} - {None, ""}
    if not _complete(ordered):
        return Rebuild(text, "incomplete", None)
    exact = chunk_text(text) == [c.get("content") or "" for c in ordered]
    hash_match = _content_hash(text) in stored_hashes if len(stored_hashes) == 1 else None
    return Rebuild(text, "rechunk_exact" if exact else "rechunk_mismatch", hash_match)


def content_hash_for(chunks: list[dict], rebuilt_text: str) -> str:
    """The stored content_hash when the chunks agree on one, else the hash of the rebuilt text."""
    stored = {c.get("content_hash") for c in chunks} - {None, ""}
    return stored.pop() if len(stored) == 1 else _content_hash(rebuilt_text)
