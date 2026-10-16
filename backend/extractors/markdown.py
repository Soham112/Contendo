"""Markdown to the extraction text contract: keep structure, drop markup.

Works on markdown syntax only (a closed grammar): links keep their text, images
and footnote-reference links go, runs of blank lines collapse. Headings, lists,
emphasis markers and table rows are left as written.
"""
import re

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
# A link whose text is a bracketed number is a footnote reference: [[1]](url)
_FOOTNOTE_LINK = re.compile(r"\[\[\d+\]\]\([^)]*\)")
# [text](url "optional title") -> text. The text may not contain brackets.
_LINK = re.compile(r"\[([^\[\]]*)\]\((?:[^()\s]|\([^()]*\))*(?:\s+\"[^\"]*\")?\)")
_AUTOLINK = re.compile(r"<https?://[^>\s]+>")
_BLANK_RUNS = re.compile(r"\n{3,}")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")


def normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _IMAGE.sub("", text)
    text = _FOOTNOTE_LINK.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _AUTOLINK.sub("", text)
    text = _TRAILING_SPACE.sub("\n", text)
    text = _BLANK_RUNS.sub("\n\n", text)
    return text.strip()
