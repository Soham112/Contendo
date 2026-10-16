"""An Obsidian note: its file text with Obsidian's own syntax removed.

Version 2 fixes three version-1 bugs: embeds (![[file]]) were turned into "!file"
text because wikilinks were rewritten first; `\\^\\w+` deleted math such as
x^2 (block ids are only " ^id" at the end of a line); [[Page|Alias]] kept the
link target, not the text the reader sees. Reading the vault stays in
tools/obsidian_tool.py.
"""
import re

from extractors.markdown import normalize_markdown
from memory.source_store import SourceOriginal

EXTRACTOR = ("obsidian_tool", "2")

_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_EMBED = re.compile(r"!\[\[[^\]]+\]\]")
_ALIASED_LINK = re.compile(r"\[\[[^\]|]+\|([^\]]+)\]\]")
_WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]]*)?\]\]")
_BLOCK_ID = re.compile(r"[ \t]+\^[A-Za-z0-9-]+[ \t]*$", re.MULTILINE)
_HIGHLIGHT = re.compile(r"==([^=\n]+)==")
_DATAVIEW = re.compile(r"```dataview.*?```", re.DOTALL)


def clean_obsidian_markdown(text: str) -> str:
    text = _FRONTMATTER.sub("", text.replace("\r\n", "\n"))
    text = _DATAVIEW.sub("", text)
    text = _EMBED.sub("", text)            # before wikilinks, which would rewrite the embed
    text = _ALIASED_LINK.sub(r"\1", text)  # the text the reader sees
    text = _WIKILINK.sub(r"\1", text)
    text = _BLOCK_ID.sub("", text)
    text = _HIGHLIGHT.sub(r"\1", text)
    return normalize_markdown(text)


def note_original(raw_content: str, relative_path: str) -> SourceOriginal:
    """The note file's text as read; clean_obsidian_markdown is the extraction."""
    return SourceOriginal(
        input_type="obsidian", extractor=EXTRACTOR[0], extractor_version=EXTRACTOR[1],
        raw_text=raw_content, raw_mime="text/markdown",
        original_filename=relative_path, title_origin="provided",
    )
