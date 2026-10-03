"""Deterministic clean-up applied to the final post."""

import re

# A model sometimes prints the word count it was asked to check ("Word count: 295").
_WORD_COUNT_LINE = re.compile(r"^\s*word count\s*:?\s*\d+.*$\n?", re.IGNORECASE | re.MULTILINE)


def strip_word_count_lines(text: str) -> str:
    """Remove any line that starts with "word count" followed by a number."""
    return _WORD_COUNT_LINE.sub("", text).strip()
