"""Shared prompt-data escaping for source blocks and serialized post sentences."""
import re

from utils.citations import escape_markers

# Source delimiters, whatever their case or spacing; structure, not meaning.
_SOURCES_TAG = re.compile(r"<(?=\s*/?\s*sources?\b)", re.IGNORECASE)


def escape_data_text(text: str, *, all_tags: bool = False) -> str:
    """Make data delimiters and marker-like text inert in a prompt.

    Sources retain their existing escaping; serialized post data escapes every
    angle bracket so it cannot forge a post or sentence delimiter.
    """
    body = text.replace("<", "&lt;").replace(">", "&gt;") if all_tags else _SOURCES_TAG.sub("&lt;", text)
    return escape_markers(body)
