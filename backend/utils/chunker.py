import re

CHUNK_SIZE_WORDS = 500
OVERLAP_WORDS = 50


def _tokenize(text: str) -> list[str]:
    return text.split()


def _join(words: list[str]) -> str:
    return " ".join(words)


def chunk_text(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    words = _tokenize(text)

    if not words:
        return []

    # If the entire text fits in one chunk, return it as-is
    if len(words) <= CHUNK_SIZE_WORDS:
        return [_join(words)]

    chunks = []
    start = 0

    while start < len(words):
        end = start + CHUNK_SIZE_WORDS
        chunk_words = words[start:end]
        chunks.append(_join(chunk_words))

        if end >= len(words):
            break

        start = end - OVERLAP_WORDS

    return chunks
