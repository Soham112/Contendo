"""Factual "specifics" in text, and a check that a rewrite added none.

A specific is a number (digits or words), percentage, money amount, duration,
month, weekday, or time phrase ("last winter", "four winters ago", "first
month"). Rewriting steps (humanizer, predictability audit) may only change
wording: every specific in their output must already be in their input draft,
the retrieved chunks, the profile, or the request's topic and context.

Equivalent forms match: "~410k SEK" = "410,000 SEK", "18 to 26%" = "18-26%",
"Nine minutes" = "9-minute". Changed values do not: "eleven pages" is not
supported by "twelve-page", and "25%" is not supported by "18-26%".

"one" is deliberately not a specific: it is too common ("one page", "no one")
to tell fact from phrasing.
"""

import re
from dataclasses import dataclass
from typing import Any, Iterable

_ONES = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_UNIT_DIGITS = {"one": 1, **{k: v for k, v in _ONES.items() if v < 10}}
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000,
           "k": 1_000, "m": 1_000_000, "bn": 1_000_000_000}

_DIGITS = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_DIGIT_SUFFIX = r"(?:(?:k|m|bn)\b|\s(?:hundred|thousand|million|billion)\b)?"
_WORD = (
    r"(?:" + "|".join(_TENS) + r")(?:[-\s](?:" + "|".join(_UNIT_DIGITS) + r"))?"
    r"|(?:" + "|".join(_ONES) + r")"
)
_WORD_SUFFIX = r"(?:\s(?:hundred|thousand|million|billion)\b)?"
_NUM = rf"(?:(?:{_DIGITS}){_DIGIT_SUFFIX}|\b(?:{_WORD})\b{_WORD_SUFFIX})"

_UNITS = {
    "ms": "millisecond", "millisecond": "millisecond", "sec": "second", "second": "second",
    "min": "minute", "minute": "minute", "hr": "hour", "hour": "hour", "day": "day",
    "week": "week", "month": "month", "quarter": "quarter", "yr": "year", "year": "year",
    "decade": "decade",
}
_SEASONS = ["winter", "spring", "summer", "autumn", "fall"]
_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]
_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_UNIT_RE = "|".join(sorted(_UNITS, key=len, reverse=True))
_PCT = r"(?:%|\s?percent\b|\s?per\s?cent\b)"
_CURRENCY_SUFFIX = r"(?:SEK|USD|EUR|GBP|kr|euros?|dollars?|pounds?)\b"

# Ordered: earlier patterns claim their span first, so "18 hours" is a duration
# and not also a bare 18.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ago", re.compile(rf"(?P<n>{_NUM})\s+(?P<u>{_UNIT_RE}|{'|'.join(_SEASONS)})s?\s+ago\b", re.I)),
    ("time", re.compile(
        rf"\b(?:last|next|past)\s+(?:{'|'.join(_SEASONS)}|year|month|week|weekend|quarter|"
        rf"{'|'.join(_MONTHS)}|{'|'.join(_WEEKDAYS)})\b"
        rf"|\b(?:first|second|third|fourth|fifth|final)\s+(?:day|week|month|year|quarter|sprint)\b", re.I)),
    # A plain hyphen only separates digit ranges ("18-26%"); "twenty-five" is one number.
    ("percent_range", re.compile(rf"(?P<a>{_NUM})(?:\s*[–—]\s*|\s+to\s+|(?<=\d)-(?=\d))(?P<b>{_NUM}){_PCT}", re.I)),
    ("percent", re.compile(rf"(?P<n>{_NUM}){_PCT}", re.I)),
    ("money", re.compile(rf"[$€£]\s?(?P<n>{_NUM})|(?P<m>{_NUM})\s?{_CURRENCY_SUFFIX}", re.I)),
    ("duration", re.compile(rf"(?P<n>{_NUM})(?:\s+|-)(?P<u>{_UNIT_RE})s?\b", re.I)),
    ("month", re.compile(rf"\b(?:{'|'.join(_MONTHS)})\b")),
    ("weekday", re.compile(rf"\b(?:{'|'.join(_WEEKDAYS)})s?\b")),
    ("number", re.compile(rf"(?<![\w.,])(?P<n>{_NUM})(?![\w])", re.I)),
]


@dataclass(frozen=True)
class Specific:
    kind: str    # number | percent | duration | ago | time | month | weekday
    text: str    # as written
    value: Any   # number value, or lowercased name/phrase
    unit: str = ""

    @property
    def key(self) -> tuple:
        return (self.kind, self.value, self.unit)

    def as_dict(self) -> dict[str, str]:
        return {"text": self.text, "kind": self.kind}


def _number_value(raw: str) -> float | None:
    s = raw.strip().lower().lstrip("~≈").strip()
    m = re.fullmatch(rf"({_DIGITS})\s?(k|m|bn|hundred|thousand|million|billion)?", s)
    if m:
        return float(m.group(1).replace(",", "")) * _SCALES.get(m.group(2) or "", 1)
    words = re.split(r"[-\s]+", s)
    scale = 1
    if len(words) > 1 and words[-1] in _SCALES:
        scale = _SCALES[words.pop()]
    total = 0
    for w in words:
        if w in _TENS:
            total += _TENS[w]
        elif w in _ONES:
            total += _ONES[w]
        elif w in _UNIT_DIGITS:
            total += _UNIT_DIGITS[w]
        else:
            return None
    return float(total * scale) if total else None


def extract_specifics(text: str) -> list[Specific]:
    """Every specific in text, in order of appearance."""
    taken: list[tuple[int, int]] = []
    found: list[tuple[int, Specific]] = []

    def free(start: int, end: int) -> bool:
        return all(end <= s or start >= e for s, e in taken)

    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if not free(m.start(), m.end()):
                continue
            raw = m.group(0)
            specifics: list[Specific] = []
            if kind == "percent_range":
                for g in ("a", "b"):
                    v = _number_value(m.group(g))
                    if v is not None:
                        specifics.append(Specific("percent", raw, v))
            elif kind in ("percent", "number"):
                v = _number_value(m.group("n"))
                if v is not None:
                    specifics.append(Specific(kind, raw, v))
            elif kind == "money":
                v = _number_value(m.group("n") or m.group("m"))
                if v is not None:
                    specifics.append(Specific("number", raw, v))
            elif kind in ("duration", "ago"):
                v = _number_value(m.group("n"))
                unit = m.group("u").lower()
                unit = _UNITS.get(unit, unit)
                if v is not None:
                    specifics.append(Specific(kind, raw, v, unit))
            elif kind == "time":
                specifics.append(Specific("time", raw, re.sub(r"\s+", " ", raw.lower())))
            else:  # month, weekday
                specifics.append(Specific(kind, raw, raw.lower().rstrip("s")))
            if specifics:
                taken.append((m.start(), m.end()))
                found.extend((m.start(), s) for s in specifics)
    found.sort(key=lambda pair: pair[0])
    return [s for _, s in found]


_DAYS_PER_UNIT = {
    "millisecond": 1 / 86_400_000, "second": 1 / 86_400, "minute": 1 / 1_440, "hour": 1 / 24,
    "day": 1, "week": 7, "month": 30, "quarter": 90, "year": 365, "decade": 3_650,
}


def _days(spec: Specific) -> float | None:
    factor = _DAYS_PER_UNIT.get(spec.unit)
    return spec.value * factor if factor is not None else None


def _supported(spec: Specific, allowed: set[tuple], allowed_values: set[float],
               allowed_days: list[float]) -> bool:
    if spec.key in allowed:
        return True
    # A bare number restating a figure the sources give in another form
    # ("26" vs "26%", "two" vs "two years").
    if spec.kind == "number":
        return spec.value in allowed_values
    # The same span of time in other units ("three months" vs "90 days"), and
    # "six days ago" when the sources say "for six days".
    if spec.kind in ("duration", "ago"):
        days = _days(spec)
        return days is not None and any(abs(days - d) <= 0.05 * max(days, d) for d in allowed_days)
    return False


def unsupported_specifics(output: str, sources: Iterable[str]) -> list[Specific]:
    """Specifics in output that no source text contains (first occurrence of each)."""
    allowed: set[tuple] = set()
    allowed_values: set[float] = set()
    allowed_days: list[float] = []
    for text in sources:
        for spec in extract_specifics(text or ""):
            allowed.add(spec.key)
            if isinstance(spec.value, float):
                allowed_values.add(spec.value)
            if spec.kind in ("duration", "ago") and (days := _days(spec)) is not None:
                allowed_days.append(days)
    missing: dict[tuple, Specific] = {}
    for spec in extract_specifics(output or ""):
        if not _supported(spec, allowed, allowed_values, allowed_days) and spec.key not in missing:
            missing[spec.key] = spec
    return list(missing.values())


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)


def grounding_texts(state: dict[str, Any], input_draft: str) -> list[str]:
    """Everything a rewrite may draw facts from: its input draft, the retrieved
    chunks, the profile, and the request's own topic and context.

    In no-specifics mode (state["no_specifics"]) only the topic, the context and
    the profile count: not the chunks, and not the input draft, so a fact the
    drafter took from the chunks is flagged rather than carried forward.
    """
    if state.get("no_specifics"):
        return [state.get("topic") or "", state.get("context") or "", *_strings(state.get("profile") or {})]
    chunks = [c.get("text") or c.get("content") or "" for c in (state.get("retrieval_bundle") or {}).get("chunks", [])]
    return [
        input_draft,
        *chunks,
        *(state.get("retrieved_chunks") or []),
        *_strings(state.get("profile") or {}),
        state.get("topic") or "",
        state.get("context") or "",
    ]


# ── Rewrite guard helpers ─────────────────────────────────────────────────────

def retry_note(violations: list[Specific], no_specifics: bool = False) -> str:
    """Prompt suffix for a rewrite's second attempt; "" when there is nothing to report."""
    if not violations:
        return ""
    listed = "\n".join(f"- {v.text}" for v in violations)
    if no_specifics:
        return (
            "\n\nThis is an opinion post without specifics. Your previous attempt included these details, "
            "which are not in the topic, the context or the author profile:\n"
            f"{listed}\n"
            "Rewrite again from the draft above without them. Keep the argument; add no other specifics."
        )
    return (
        "\n\nYour previous attempt added or changed these details, which are not in the draft or its sources:\n"
        f"{listed}\n"
        "Rewrite again from the draft above. Keep every factual detail exactly as the draft states it, and add none."
    )


def guard_entry(node: str, iteration: int, first: list[Specific], second: list[Specific] | None) -> dict[str, Any]:
    """One specifics_guard trace entry for a node run that needed a retry.

    outcome: "accepted_after_retry" (the retry was clean) or "reverted" (the
    retry still added facts, so the node's input draft was kept).
    """
    return {
        "node": node,
        "iteration": iteration,
        "first_attempt": [v.as_dict() for v in first],
        "retry": [v.as_dict() for v in (second or [])],
        "outcome": "reverted" if second else "accepted_after_retry",
    }
