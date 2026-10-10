"""Citation markers: how a draft says where each of its spans came from.

The drafter ends every prose span with exactly one marker:

    [[S2]]      supported by source S2 (ids as utils.frames.build_sources_block gives them)
    [[S1,S3]]   supported by both sources
    [[R]]       stated in the request (the topic or the additional context)
    [[V]]       the author's view or reasoning, with no factual claim

A span is the text on one line between the previous marker (or the start of the
line) and its own marker, so code never has to split model prose into sentences.
Text with no marker is an "uncited" span. Headings, [DIAGRAM: ...] / [IMAGE: ...]
lines and code are structure, not prose: they need no marker and give no span.

For a story post the draft starts with one EVENT line naming the event it
tells (parse_event_header):

    EVENT: S3 | "a sentence copied word for word from that source"
    EVENT: none          no source describes an event that fits the topic

Markers and the EVENT line are formats this codebase defines, so they are
matched exactly. Nothing here judges what a span means, whether its sources
support it, or whether the quoted sentence is really in the source.
"""

import re
from dataclasses import dataclass
from typing import Collection, Sequence

from utils.text_spans import protected_spans

REQUEST = "R"
VIEW = "V"

_SOURCE_ID = r"S[1-9]\d*"
# Deliberate tolerance: spaces around the ids and commas ("[[S1, S3]]").
_VALID_INNER = re.compile(
    rf"[ \t]*(?:(?P<sources>{_SOURCE_ID}(?:[ \t]*,[ \t]*{_SOURCE_ID})*)|(?P<basis>{REQUEST}|{VIEW}))[ \t]*"
)
# Anything shaped like a marker, tried in this order at each position:
#   double  [[...]] on one line, valid or not
#   single  a marker's contents in single brackets ("[S3]", "[V]")
#   stray   an opening or closing pair with no partner
_MARKER_LIKE = re.compile(
    r"(?P<double>\[\[(?P<inner>[^\[\]\n]*)\]\])"
    r"|(?P<single>\[[ \t]*(?:S\d+(?:[ \t]*,[ \t]*S\d+)*|R|V)[ \t]*\])"
    r"|(?P<stray>\[\[|\]\])"
)
# Closing punctuation written straight after a marker ("...fell [[S1]].") stays
# with the span the marker ends.
_CLOSING = ".,;:!?)\"'”’"
_HEADING = re.compile(r"#{1,6}[ \t]")
_PLACEHOLDER = re.compile(r"\[(?:DIAGRAM|IMAGE):.*\]")


def source_id(position: int) -> str:
    """The id of the source at this 0-based position in the retrieval bundle: S1, S2, ..."""
    return f"S{position + 1}"


@dataclass(frozen=True)
class Span:
    """One span of the clean text: text == clean[start:end]."""
    start: int
    end: int
    text: str
    basis: str                 # "sources" | "request" | "view" | "uncited"
    sources: tuple[str, ...]   # the cited S-ids when basis is "sources", else ()

    def as_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "text": self.text,
                "basis": self.basis, "sources": list(self.sources)}

    @classmethod
    def from_dict(cls, data: dict) -> "Span":
        return cls(data["start"], data["end"], data["text"], data["basis"], tuple(data["sources"]))


@dataclass(frozen=True)
class MarkerFailure:
    """Marker-like text that is not a usable citation.

    kind: "malformed" (double brackets around something that is not S-ids, R or V),
    "single_brackets", "unbalanced" (an opening or closing pair alone),
    "empty_span" (a marker with no prose before it), or "leftover" (a valid
    marker found in text that should have none). start/end are offsets in the
    text that was scanned.
    """
    kind: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class StrippedPost:
    text: str                           # the post without markers
    spans: tuple[Span, ...]             # in order, uncited ones included
    failures: tuple[MarkerFailure, ...]


@dataclass(frozen=True)
class _Token:
    start: int
    end: int
    text: str
    kind: str                           # "valid" | "malformed" | "single_brackets" | "unbalanced"
    basis: str = ""
    sources: tuple[str, ...] = ()


def _token(match: re.Match, offset: int) -> _Token:
    start, end, text = offset + match.start(), offset + match.end(), match.group(0)
    if match.group("single"):
        return _Token(start, end, text, "single_brackets")
    if match.group("stray"):
        return _Token(start, end, text, "unbalanced")
    inner = _VALID_INNER.fullmatch(match.group("inner"))
    if not inner:
        return _Token(start, end, text, "malformed")
    if inner.group("basis"):
        return _Token(start, end, text, "valid", "request" if inner.group("basis") == REQUEST else "view")
    ids = tuple(dict.fromkeys(part.strip() for part in inner.group("sources").split(",")))
    return _Token(start, end, text, "valid", "sources", ids)


def _scan(text: str, *, include_protected: bool) -> list[_Token]:
    """Every marker-like token, in order. Code, URLs, link destinations and HTML
    (utils.text_spans.protected_spans) are skipped unless include_protected."""
    tokens: list[_Token] = []
    cursor = 0
    for start, end in ([] if include_protected else protected_spans(text, quoted_literals=False)):
        tokens.extend(_token(m, cursor) for m in _MARKER_LIKE.finditer(text[cursor:start]))
        cursor = end
    tokens.extend(_token(m, cursor) for m in _MARKER_LIKE.finditer(text[cursor:]))
    return tokens


def leftover_markers(text: str, *, include_protected: bool = False) -> list[MarkerFailure]:
    """Marker-like text in a string that should contain none (a final post, a
    rendered source). A valid marker is reported as "leftover"."""
    return [
        MarkerFailure("leftover" if t.kind == "valid" else t.kind, t.text, t.start, t.end)
        for t in _scan(text, include_protected=include_protected)
    ]


def escape_markers(text: str) -> str:
    """text with every marker-like sequence made inert: its brackets become the
    character references &#91; and &#93;. For source text shown to a model, so
    nothing a source contains can be read, or copied out, as a citation. Applies
    inside code too: a source's own Markdown gives no protection in a prompt."""
    pieces, cursor = [], 0
    for token in _scan(text, include_protected=True):
        pieces.append(text[cursor:token.start])
        pieces.append(token.text.replace("[", "&#91;").replace("]", "&#93;"))
        cursor = token.end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _remove_markers(text: str, tokens: list[_Token]) -> tuple[str, list[tuple[int, _Token]]]:
    """The text without its double-bracket markers (and the spaces before each),
    and where each one stood in that text. Single-bracket and unbalanced tokens
    are not markers anyone can act on: they stay in the text and are reported."""
    pieces: list[str] = []
    boundaries: list[tuple[int, _Token]] = []
    cursor = length = 0
    for token in tokens:
        if token.kind not in ("valid", "malformed"):
            continue
        kept = text[cursor:token.start].rstrip(" \t") if token.start > cursor else ""
        pieces.append(kept)
        length += len(kept)
        boundaries.append((length, token))
        cursor = token.end
    pieces.append(text[cursor:])
    return "".join(pieces), boundaries


def _is_prose(clean: str, start: int, end: int, protected: list[tuple[int, int]]) -> bool:
    """Whether clean[start:end] has a letter or digit outside code, URLs and HTML."""
    return any(
        clean[i].isalnum() and not any(s <= i < e for s, e in protected)
        for i in range(start, end)
    )


def _is_structural(line: str) -> bool:
    stripped = line.strip()
    return bool(_HEADING.match(stripped) or _PLACEHOLDER.fullmatch(stripped))


def strip_citations(text: str) -> StrippedPost:
    """Split a marked draft into the clean post, its spans and any marker failures.

    Every double-bracket marker is removed from the text, valid or not; a span
    whose marker is malformed is returned as uncited. Offsets in spans are into
    the clean text; offsets in failures are into the marked text given.
    """
    tokens = _scan(text, include_protected=False)
    clean, boundaries = _remove_markers(text, tokens)
    protected = protected_spans(clean, quoted_literals=False)
    failures = [MarkerFailure(t.kind, t.text, t.start, t.end) for t in tokens if t.kind != "valid"]
    spans: list[Span] = []

    def add(start: int, end: int, token: _Token | None, structural: bool) -> None:
        if not _is_prose(clean, start, end, protected):
            if token is not None and token.kind == "valid":
                failures.append(MarkerFailure("empty_span", token.text, token.start, token.end))
            return
        cited = token is not None and token.kind == "valid"
        if not cited and structural:
            return
        body = clean[start:end]
        lead = len(body) - len(body.lstrip())
        body = body.strip()
        spans.append(Span(start + lead, start + lead + len(body), body,
                          token.basis if cited else "uncited", token.sources if cited else ()))

    line_start, pending = 0, list(boundaries)
    for line in clean.splitlines(keepends=True) or [""]:
        line_end = line_start + len(line.rstrip("\r\n"))
        structural = _is_structural(clean[line_start:line_end])
        cursor = line_start
        while pending and pending[0][0] <= line_end:
            position, token = pending.pop(0)
            while position < line_end and clean[position] in _CLOSING:
                position += 1
            add(cursor, position, token, structural)
            cursor = position
        add(cursor, line_end, None, structural)
        line_start += len(line)

    failures.sort(key=lambda f: (f.start, f.end))
    return StrippedPost(clean, tuple(spans), tuple(failures))


def delete_spans(text: str, spans: Sequence[Span], delete: Collection[int]) -> tuple[str, tuple[Span, ...]]:
    """text without the spans at the given positions in `spans`, and the
    remaining spans with their offsets in the new text.

    Only whole spans go; nothing is reworded. Spans never cross a line, so the
    work is per line: the spans kept on a line are joined by single spaces, and a
    line left with no content is dropped, with one of the blank lines around it
    so no double gap is left. Lines that hold no span (headings, placeholders,
    code, blank lines) are untouched.
    """
    lines = text.split("\n")
    starts, offset = [], 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1
    on_line: dict[int, list[int]] = {}
    for index, span in enumerate(spans):
        row = max(i for i, start in enumerate(starts) if start <= span.start)
        on_line.setdefault(row, []).append(index)

    out: list[list[tuple[str, Span | None]]] = []   # one list of (text, span) pieces per kept line
    skip_blank = False
    for row, line in enumerate(lines):
        if skip_blank and not line.strip():
            skip_blank = False
            continue
        skip_blank = False
        if row not in on_line:
            out.append([(line, None)])
            continue
        start = cursor = starts[row]
        first = spans[on_line[row][0]]
        pieces: list[tuple[str, Span | None]] = []
        for index in on_line[row]:
            span = spans[index]
            between = text[cursor:span.start].strip()
            if between:
                pieces.append((between, None))
            if index not in delete:
                pieces.append((span.text, span))
            cursor = span.end
        after = text[cursor:start + len(line)].strip()
        if after:
            pieces.append((after, None))
        if pieces:
            indent = text[start:first.start] if not text[start:first.start].strip() else ""
            out.append([(indent, None), *pieces] if indent else pieces)
            continue
        # The line is gone. Close the gap it leaves between blank lines.
        last_is_blank = not out or not "".join(t for t, _ in out[-1]).strip()
        if row + 1 < len(lines):
            skip_blank = last_is_blank and not lines[row + 1].strip()
        elif out and last_is_blank:
            out.pop()

    built: list[str] = []
    kept: list[Span] = []
    length = 0
    for row, pieces in enumerate(out):
        if row:
            built.append("\n")
            length += 1
        previous_was_content = False
        for piece, span in pieces:
            if previous_was_content:
                built.append(" ")
                length += 1
            built.append(piece)
            if span is not None:
                kept.append(Span(length, length + len(piece), piece, span.basis, span.sources))
            length += len(piece)
            previous_was_content = bool(piece.strip())
    return "".join(built), tuple(kept)


# ── The EVENT line ────────────────────────────────────────────────────────────

_EVENT_PREFIX = "EVENT:"
EVENT_NONE = "none"
# Straight or curly double quotes around the copied sentence: a deliberate
# tolerance. The sentence itself may contain quotation marks.
_EVENT_CITED = re.compile(rf"(?P<source>{_SOURCE_ID})[ \t]*\|[ \t]*[\"“](?P<quote>.*\S.*)[\"”]")


@dataclass(frozen=True)
class EventHeader:
    """What a draft's EVENT line says.

    status:
      "cited"       names a source and quotes a sentence (source, quote set)
      "none"        the drafter found no event that fits ("EVENT: none")
      "absent"      no EVENT line, and none was required
      "missing"     no EVENT line on a post type that requires one   (failure)
      "malformed"   an EVENT line that is neither form                (failure)
      "unexpected"  an EVENT line on a post type that takes none      (failure)
    line is the EVENT line as written ("" when there is none). body is the draft
    without it: the EVENT line never stays in the post, whatever its status.
    """
    status: str
    source: str | None
    quote: str | None
    line: str
    body: str

    @property
    def failed(self) -> bool:
        return self.status in ("missing", "malformed", "unexpected")


def parse_event_header(text: str, *, required: bool) -> EventHeader:
    """Read and remove the EVENT line, which is the draft's first non-empty line.

    required: the post type tells an event (a story archetype). Whether the
    quoted sentence is in the cited source is checked elsewhere.
    """
    lines = text.splitlines(keepends=True)
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None or not lines[first].strip().startswith(_EVENT_PREFIX):
        return EventHeader("missing" if required else "absent", None, None, "", text)

    line = lines[first].strip()
    body = "".join(lines[first + 1:]).lstrip("\r\n")
    value = line[len(_EVENT_PREFIX):].strip()
    if not required:
        return EventHeader("unexpected", None, None, line, body)
    if value == EVENT_NONE:
        return EventHeader("none", None, None, line, body)
    cited = _EVENT_CITED.fullmatch(value)
    if not cited:
        return EventHeader("malformed", None, None, line, body)
    return EventHeader("cited", cited.group("source"), cited.group("quote").strip(), line, body)
