"""Whether two short pieces of wording say the same thing in a different form.

same_wording() is true when the two differ only in ways English fixes: case,
whitespace, straight or curly apostrophes, a number in words or in digits, and
a contraction or its full form. These are closed sets given by the language, not
lists of things someone chose. Anything else, including a synonym, is a
difference: this never judges meaning.
"""

import itertools
import re

# Number words. "one" is here although utils.specifics leaves it out as too
# common to be a fact: here the only question is whether "one" and "1" are the
# same wording, and they are.
_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
          "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
          "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_NUMBER_WORD = "|".join([*_UNITS, *_TENS, *_SCALES])
_NUMBER_WORDS = re.compile(rf"\b(?:{_NUMBER_WORD})(?:(?:[-\s]|\sand\s)(?:{_NUMBER_WORD}))*\b")
_DIGITS = re.compile(r"\d{1,3}(?:,\d{3})+|\d+")

# Contractions with one full form.
_IRREGULAR = {"can't": "can not", "cannot": "can not", "won't": "will not", "shan't": "shall not"}
_SUFFIXES = (("n't", " not"), ("'re", " are"), ("'ve", " have"), ("'ll", " will"), ("'m", " am"))
# Contractions with more than one full form: every reading is tried.
_AMBIGUOUS = {"'s": (" is", " has", "'s"), "'d": (" would", " had")}
_AMBIGUOUS_RE = re.compile(r"(?<=\w)'(?:s|d)\b")
# More ambiguous contractions than this in one piece of wording and only the
# first few are expanded: the pieces compared are a few words long.
_MAX_AMBIGUOUS = 4


def _number_words_to_digits(text: str) -> str:
    def value(match: re.Match) -> str:
        total = current = 0
        for word in re.split(r"[-\s]+", match.group(0)):
            if word == "and":
                continue
            if word in _UNITS:
                current += _UNITS[word]
            elif word in _TENS:
                current += _TENS[word]
            elif word == "hundred":
                current = (current or 1) * 100
            else:
                total += (current or 1) * _SCALES[word]
                current = 0
        return str(total + current)
    return _NUMBER_WORDS.sub(value, text)


def _base_form(text: str) -> str:
    """Lower case, one space between words, straight apostrophes, numbers as
    plain digits, and every contraction with a single full form expanded."""
    text = re.sub(r"\s+", " ", (text or "").replace("’", "'").replace("‘", "'")).strip().lower()
    text = _DIGITS.sub(lambda m: m.group(0).replace(",", ""), text)
    text = _number_words_to_digits(text)
    for short, full in _IRREGULAR.items():
        text = re.sub(rf"\b{re.escape(short)}\b", full, text)
    for suffix, full in _SUFFIXES:
        text = re.sub(rf"(?<=\w){re.escape(suffix)}\b", full, text)
    return text


def _readings(text: str) -> set[str]:
    """Every way of reading the ambiguous contractions left in a base form."""
    spots = [m.span() for m in _AMBIGUOUS_RE.finditer(text)][:_MAX_AMBIGUOUS]
    if not spots:
        return {text}
    readings = set()
    for choice in itertools.product(*[_AMBIGUOUS[text[a:b]] for a, b in spots]):
        pieces, cursor = [], 0
        for (a, b), full in zip(spots, choice):
            pieces += [text[cursor:a], full]
            cursor = b
        readings.add("".join(pieces) + text[cursor:])
    return readings


def same_wording(first: str, second: str) -> bool:
    """Whether the two are the same words in a different form (see the module docstring)."""
    return bool(_readings(_base_form(first)) & _readings(_base_form(second)))


def same_sentence(first: str, second: str) -> bool:
    """same_wording(), with the punctuation and spaces at either end of each
    left aside: whether a quoted run of words is the whole of a sentence."""
    def inner(text: str) -> str:
        start = next((i for i, char in enumerate(text) if char.isalnum()), len(text))
        end = next((i for i in range(len(text), start, -1) if text[i - 1].isalnum()), start)
        return text[start:end]
    return same_wording(inner(first or ""), inner(second or ""))
