"""The drafter's output envelope: tags this codebase defines, matched exactly.

A draft (first draft or full redraft) is

    <event>S3 | "a sentence copied word for word from that source"</event>
    <post>
    the post, with its citation markers
    </post>

The <event> part is there only for a story post: it names the event the post
tells, or is <event>none</event> when no source describes an event that fits
the topic. Everything outside the tags is not part of the post: it is dropped
and reported as a format failure, so a preamble or a separator line the model
adds can never reach the author.

A targeted fix (variant B) is a list of replacements for numbered sentences:

    <fixes>
    <fix sentence="4">replacement sentence, with its marker</fix>
    <fix sentence="7" delete="true"/>
    </fixes>

Nothing here judges content: whether the quoted sentence is in the source, or
whether a fix is for a sentence that had a problem, is checked elsewhere.
"""

import re
from dataclasses import dataclass

from utils.citations import SOURCE_ID_PATTERN

EVENT_NONE = "none"
_POST_OPEN, _POST_CLOSE = "<post>", "</post>"
_EVENT = re.compile(r"<event>(.*?)</event>", re.DOTALL)
# Straight or curly double quotes around the copied sentence: a deliberate
# tolerance. The sentence itself may contain quotation marks.
_EVENT_CITED = re.compile(rf"(?P<source>{SOURCE_ID_PATTERN})[ \t]*\|[ \t]*[\"“](?P<quote>.*\S.*)[\"”]")
_FIXES = re.compile(r"<fixes>(.*)</fixes>", re.DOTALL)
_FIX = re.compile(r'<fix\s+sentence="(?P<number>\d+)"(?P<delete>\s+delete="true")?\s*(?:/>|>(?P<text>.*?)</fix>)',
                  re.DOTALL)


@dataclass(frozen=True)
class DraftOutput:
    """What a draft's envelope held.

    status (the event):
      "cited"       names a source and quotes a sentence (source, quote set)
      "none"        the drafter found no event that fits (<event>none</event>)
      "absent"      no <event> part, and none was required
      "missing"     no <event> part on a post type that requires one   (failure)
      "malformed"   an <event> part that is neither form                (failure)
      "unexpected"  an <event> part on a post type that takes none      (failure)
    line is what the <event> part held ("" when there is none). body is the
    post: what stood between <post> and </post>. format_failures lists what
    broke the envelope, each {kind, text}:
      "text_outside_tags"   text before, between or after the tagged parts (dropped)
      "event_repeated"      a second <event> part (dropped; the first counts)
      "post_unclosed"       <post> with no </post>: the post runs to the end
      "post_tag_missing"    no <post> at all: everything outside <event> is taken as the post
    """
    status: str
    source: str | None
    quote: str | None
    line: str
    body: str
    format_failures: tuple[dict, ...]

    @property
    def failed(self) -> bool:
        return self.status in ("missing", "malformed", "unexpected")


def _event(parts: list[str], story: bool) -> tuple[str, str | None, str | None, str]:
    """(status, source, quote, line) from the <event> parts found."""
    if not parts:
        return ("missing" if story else "absent"), None, None, ""
    line = parts[0].strip()
    if not story:
        return "unexpected", None, None, line
    if line == EVENT_NONE:
        return "none", None, None, line
    cited = _EVENT_CITED.fullmatch(line)
    if not cited:
        return "malformed", None, None, line
    return "cited", cited.group("source"), cited.group("quote").strip(), line


def parse_draft_output(text: str, *, story: bool) -> DraftOutput:
    """Read a draft's envelope. story: the post type tells an event, so the
    <event> part is required."""
    failures: list[dict] = []
    opened = text.find(_POST_OPEN)
    if opened == -1:
        outside, body = [text], None
        failures.append({"kind": "post_tag_missing", "text": ""})
    else:
        closed = text.rfind(_POST_CLOSE, opened)
        if closed == -1:
            failures.append({"kind": "post_unclosed", "text": ""})
            outside, body = [text[:opened]], text[opened + len(_POST_OPEN):]
        else:
            outside, body = [text[:opened], text[closed + len(_POST_CLOSE):]], text[opened + len(_POST_OPEN):closed]

    events: list[str] = []
    stray: list[str] = []
    for segment in outside:
        cursor = 0
        for match in _EVENT.finditer(segment):
            stray.append(segment[cursor:match.start()])
            events.append(match.group(1))
            cursor = match.end()
        stray.append(segment[cursor:])
    leftover = [piece.strip() for piece in stray if piece.strip()]
    if body is None:                         # no <post>: the text that is not an event is all there is
        body = "\n\n".join(leftover)
    else:
        failures += [{"kind": "text_outside_tags", "text": piece} for piece in leftover]
    failures += [{"kind": "event_repeated", "text": extra.strip()} for extra in events[1:]]
    status, source, quote, line = _event(events, story)
    return DraftOutput(status, source, quote, line, body.strip("\r\n"), tuple(failures))


@dataclass(frozen=True)
class Fix:
    sentence: int              # the sentence's number, as numbered in the prompt (1-based)
    text: str | None           # the replacement, with its markers; None to leave the sentence out


def parse_fixes(text: str) -> tuple[list[Fix], list[dict]]:
    """The fixes in a targeted-fix answer, in the order given, and what broke
    the format ({kind, text}): "fixes_tag_missing" (nothing can be read), or
    "text_outside_fix" (text inside <fixes> that is not a <fix>; ignored)."""
    block = _FIXES.search(text)
    if not block:
        return [], [{"kind": "fixes_tag_missing", "text": text.strip()}]
    fixes: list[Fix] = []
    failures: list[dict] = []
    cursor, inner = 0, block.group(1)
    for match in _FIX.finditer(inner):
        between = inner[cursor:match.start()].strip()
        if between:
            failures.append({"kind": "text_outside_fix", "text": between})
        deleted = bool(match.group("delete"))
        fixes.append(Fix(int(match.group("number")), None if deleted else (match.group("text") or "").strip()))
        cursor = match.end()
    if inner[cursor:].strip():
        failures.append({"kind": "text_outside_fix", "text": inner[cursor:].strip()})
    return fixes, failures
