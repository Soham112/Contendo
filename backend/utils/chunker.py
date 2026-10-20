import re
from dataclasses import dataclass

CHUNK_SIZE_WORDS = 500
OVERLAP_WORDS = 50

# A word is a run of non-whitespace: exactly the tokens str.split() gives.
_WORD = re.compile(r"\S+")


def _tokenize(text: str) -> list[str]:
    return text.split()


def _join(words: list[str]) -> str:
    return " ".join(words)


@dataclass(frozen=True)
class ChunkSpan:
    text: str     # the chunk as stored: its words joined by single spaces
    start: int    # offsets into the chunked text: its first word starts at start,
    end: int      # its last word ends at end


def chunk_spans(text: str) -> list[ChunkSpan]:
    """Chunks with their character offsets into `text` (sources.extracted_text),
    so offset-based labels (provenance spans) can be mapped onto chunks."""
    words = list(_WORD.finditer(text))
    if not words:
        return []

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE_WORDS, len(words))
        piece = words[start:end]
        chunks.append(ChunkSpan(_join([w.group() for w in piece]), piece[0].start(), piece[-1].end()))
        if end >= len(words):
            break
        start = end - OVERLAP_WORDS
    return chunks


def chunk_text(text: str) -> list[str]:
    return [chunk.text for chunk in chunk_spans(text)]
