"""What the author may see of a draft while it is still being written.

The drafter's raw output is an envelope (utils/draft_output.py: <structure>,
<event>, then the post between <post> and </post>) whose prose carries citation
markers (utils/citations.py: [[S2]], [[R]], ...). A preview shows only the post,
without its markers, and only the part of it that later text cannot change:

- nothing before <post> (the structure and event parts) and nothing from </post> on;
- a marker is shown to no one: an unclosed "[[" is held back until it closes or
  its line ends, and a closed marker is dropped with the spaces before it;
- spaces at the end are held back (they may sit before a marker), and so is a
  tail that may be the start of "[[" or "</post>".

So each preview of a longer raw text starts with the preview of a shorter one,
and DraftPreview can send only what is new. The preview is not the post: the
pipeline still parses, normalises and checks the full draft, and its result
replaces the preview.
"""

import re

_POST_OPEN, _POST_CLOSE = "<post>", "</post>"
# A closed marker on one line, with the spaces before it (utils.citations,
# _MARKER_LIKE "double": valid and invalid markers alike are hidden).
_MARKER = re.compile(r"[ \t]*\[\[[^\[\]\n]*\]\]")
_TRAILING_SPACE = re.compile(r"[ \t]+$")


def preview_text(raw: str) -> str:
    """The settled visible post in a partial raw draft ("" before <post>)."""
    start = raw.find(_POST_OPEN)
    if start < 0:
        return ""
    body = raw[start + len(_POST_OPEN):]
    end = body.find(_POST_CLOSE)
    if end >= 0:
        body = body[:end]
    else:
        body = body[:len(body) - _partial_suffix(body, _POST_CLOSE)]
    body = body[:_unclosed_marker(body)]
    if body.endswith("[") and end < 0:
        body = body[:-1]
    body = _TRAILING_SPACE.sub("", _MARKER.sub("", body)).lstrip()
    # Whole trailing blank lines stay held too: the post may end there.
    return body.rstrip("\n") if end < 0 else body.rstrip()


def _partial_suffix(text: str, tag: str) -> int:
    """Length of the longest end of text that is a start of tag (not all of it)."""
    for size in range(min(len(tag) - 1, len(text)), 0, -1):
        if text.endswith(tag[:size]):
            return size
    return 0


def _unclosed_marker(body: str) -> int:
    """Where an unclosed "[[" on the last line starts (len(body) when none)."""
    line_start = body.rfind("\n") + 1
    opening = body.rfind("[[", line_start)
    if opening < 0 or "]]" in body[opening:]:
        return len(body)
    return opening


class DraftPreview:
    """Feed the raw draft as it streams; get back only newly settled text."""

    def __init__(self) -> None:
        self._raw: list[str] = []
        self._sent = 0

    def feed(self, delta: str) -> str:
        self._raw.append(delta)
        visible = preview_text("".join(self._raw))
        new, self._sent = visible[self._sent:], max(self._sent, len(visible))
        return new
