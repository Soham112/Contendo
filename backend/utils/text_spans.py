"""Original literal offsets, using the existing markdown-it-py parser.

Block maps protect fenced/indented code, HTML and reference definitions. Wrapped
inline rules retain offsets that rendered tokens normally discard, protecting
backticks, autolinks, HTML and link/image destinations without rewriting source.
Bare URLs and quote-delimited plain-text literals use lexical patterns; neither
pattern infers meaning. Quote spans are optional for sentence segmentation.
"""
import re

from markdown_it import MarkdownIt
from markdown_it.rules_inline import autolink, backtick, html_inline, image, link

_URL = re.compile(r"(?:https?://|ftp://|mailto:|www\.)[^\s<>\"']+", re.IGNORECASE)
_STRING = re.compile(r"(?<!\w)(?P<quote>[\"'])(?:\\.|(?!(?P=quote))[^\n])*(?P=quote)")


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _capture(rule, kind: str, spans: list[tuple[int, int]]):
    """Observe successful parser rules; parser owns delimiter/escape handling."""
    def wrapped(state, silent: bool) -> bool:
        start, count = state.pos, len(state.tokens)
        label_end = -1
        if not silent and kind in {"link", "image"}:
            opener = start + 1 if kind == "image" else start
            label_end = state.md.helpers.parseLinkLabel(state, opener, True)
        matched = rule(state, silent)
        if matched and not silent:
            if kind in {"link", "image"}:
                # Preserve destinations/titles while leaving label prose editable.
                if label_end >= 0 and state.src[label_end + 1:label_end + 2] == "(":
                    spans.append((label_end + 1, state.pos))
            elif kind != "backticks" or any(t.type == "code_inline" for t in state.tokens[count:]):
                spans.append((start, state.pos))
        return matched
    return wrapped


def protected_spans(text: str, *, quoted_literals: bool = True) -> list[tuple[int, int]]:
    """Sorted, non-overlapping intervals, copied verbatim by typography.

    A parser instance is local to the call; inline state is never shared across
    requests. Protected blocks are masked at equal length for inline parsing.
    """
    parser = MarkdownIt("commonmark")
    environment, blocks, spans = {}, [], []
    parser.block.parse(text, parser, environment, blocks)
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    for token in blocks:
        if token.type in {"fence", "code_block", "html_block"} and token.map:
            spans.append((offsets[token.map[0]], offsets[token.map[1]]))
    for reference in environment.get("references", {}).values():
        start, end = reference["map"]
        spans.append((offsets[start], offsets[end]))

    masked = list(text)
    for start, end in spans:
        masked[start:end] = " " * (end - start)
    for name, rule in (("backticks", backtick), ("link", link), ("image", image),
                       ("autolink", autolink), ("html_inline", html_inline)):
        parser.inline.ruler.at(name, _capture(rule, name, spans))
    parser.inline.parse("".join(masked), parser, environment, [])
    # Bare URLs have no mandatory Markdown delimiters. Keep their bytes intact;
    # trailing sentence punctuation is not part of the URL's protected interval.
    for match in _URL.finditer(text):
        end = match.end()
        while end > match.start() and text[end - 1] in ".,;!?":
            end -= 1
        spans.append((match.start(), end))
    if quoted_literals:
        spans.extend(match.span() for match in _STRING.finditer(text))
    return _merge(spans)
