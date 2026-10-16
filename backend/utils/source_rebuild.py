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

from utils.chunker import CHUNK_SIZE_WORDS, OVERLAP_WORDS, _join, _tokenize, chunk_text

CHUNKER_VERSION = "chunker_v1"


@dataclass(frozen=True)
class Rebuild:
    text: str
    check: str               # rechunk_exact | rechunk_mismatch | incomplete
    hash_match: bool | None  # None when there is no stored hash to compare


def _content_hash(text: str) -> str:
    # Same normalisation as ingestion_agent.compute_content_hash.
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


def total_recorded(chunks: list[dict]) -> bool:
    """False when total_chunks is NULL or 0 on every row. A source with stored
    chunks can't have 0 of them: rows moved from ChromaDB (2026-04-19, commit
    b9c0d91) got 0 when the old metadata had no total."""
    return any((c.get("total_chunks") or 0) > 0 for c in chunks)


def _complete(chunks: list[dict]) -> bool:
    """Indexes 0..n-1 each exactly once, and n is known to be the whole source:
    every row records the same total n, or (total not recorded) the last chunk
    is shorter than a full window, which chunker_v1 only produces at the end."""
    if any(c.get("chunk_index") is None for c in chunks):
        return False
    indexes = sorted(c["chunk_index"] for c in chunks)
    if indexes != list(range(len(chunks))):
        return False
    if not total_recorded(chunks):
        last = max(chunks, key=lambda c: c["chunk_index"])
        return len(_tokenize(last.get("content") or "")) < CHUNK_SIZE_WORDS
    return {c.get("total_chunks") for c in chunks} == {len(chunks)}


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
