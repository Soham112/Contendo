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

Markers are a format this codebase defines, so they are matched exactly. Nothing
here judges what a span means or whether its sources support it.
"""

import re
from dataclasses import dataclass

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
