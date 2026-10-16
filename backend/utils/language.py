"""The language of a source's text, checked at ingestion.

The embedder (all-MiniLM-L6-v2, memory/vector_store.py) is English-only: text in
another language is stored but can't be found by meaning. Every source's
extracted text is identified here before it is stored, and a source confidently
in an unsupported language is refused (agents/ingestion_agent.ingest_content).

Identification is statistical: py3langid (BSD-3-Clause), a naive Bayes model
over byte n-grams covering 97 languages, deterministic and local. Code and
identifiers are removed by syntax first, because the model reads them as Latin
or Dutch, and symbols (♪, arrows, emoji) are removed and case folded, because
the model reads bytes and all-caps lyrics between ♪ read as Gujarati. Short text is undetermined rather than guessed: below MIN_BYTES, or
below MIN_CONFIDENCE, the result is None and the source is accepted. Size is
counted in UTF-8 bytes, the unit the model reads, so the floor is fair across
scripts (a Chinese character is 3 bytes and carries more than a Latin letter).
A provider's reported language (Supadata's `lang`) is used only when the text
itself is undetermined.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

logger = logging.getLogger(__name__)

SUPPORTED = frozenset({"en"})   # what the embedder can search
DEFAULT = "en"                  # the language asked of providers (no profile setting exists yet)

# Measured on the repo's English docs split into paragraphs and sentences (about
# 3,200 samples) and passed through prose(): under 80 bytes about 0.7% were
# identified as another language with confidence 0.9 or more, at 80-160 bytes one
# table fragment was, from 160 bytes up none were (about 650 samples). Refusing
# English is worse than accepting a short foreign note, so the floor keeps a margin.
MIN_BYTES = 300
MIN_CONFIDENCE = 0.9

_FENCED = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_URL = re.compile(r"\S+://\S+")
# An ASCII token shaped like code: snake_case, digits, camelCase, a.b, a/b.
_IDENTIFIER = re.compile(r"[A-Za-z0-9_./-]*(?:_|\d|[a-z][A-Z]|[A-Za-z]\.[A-Za-z]|/)[A-Za-z0-9_./-]*")

# ISO 639-1 names for the codes py3langid returns (a closed, standard set).
NAMES = {
    "af": "Afrikaans", "am": "Amharic", "an": "Aragonese", "ar": "Arabic", "as": "Assamese",
    "az": "Azerbaijani", "be": "Belarusian", "bg": "Bulgarian", "bn": "Bengali", "br": "Breton",
    "bs": "Bosnian", "ca": "Catalan", "cs": "Czech", "cy": "Welsh", "da": "Danish", "de": "German",
    "dz": "Dzongkha", "el": "Greek", "en": "English", "eo": "Esperanto", "es": "Spanish",
    "et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish", "fo": "Faroese",
    "fr": "French", "ga": "Irish", "gl": "Galician", "gu": "Gujarati", "he": "Hebrew", "hi": "Hindi",
    "hr": "Croatian", "ht": "Haitian Creole", "hu": "Hungarian", "hy": "Armenian", "id": "Indonesian",
    "is": "Icelandic", "it": "Italian", "ja": "Japanese", "jv": "Javanese", "ka": "Georgian",
    "kk": "Kazakh", "km": "Khmer", "kn": "Kannada", "ko": "Korean", "ku": "Kurdish", "ky": "Kyrgyz",
    "la": "Latin", "lb": "Luxembourgish", "lo": "Lao", "lt": "Lithuanian", "lv": "Latvian",
    "mg": "Malagasy", "mk": "Macedonian", "ml": "Malayalam", "mn": "Mongolian", "mr": "Marathi",
    "ms": "Malay", "mt": "Maltese", "nb": "Norwegian Bokmål", "ne": "Nepali", "nl": "Dutch",
    "nn": "Norwegian Nynorsk", "no": "Norwegian", "oc": "Occitan", "or": "Odia", "pa": "Punjabi",
    "pl": "Polish", "ps": "Pashto", "pt": "Portuguese", "qu": "Quechua", "ro": "Romanian",
    "ru": "Russian", "rw": "Kinyarwanda", "se": "Northern Sami", "si": "Sinhala", "sk": "Slovak",
    "sl": "Slovenian", "sq": "Albanian", "sr": "Serbian", "sv": "Swedish", "sw": "Swahili",
    "ta": "Tamil", "te": "Telugu", "th": "Thai", "tl": "Tagalog", "tr": "Turkish", "ug": "Uyghur",
    "uk": "Ukrainian", "ur": "Urdu", "vi": "Vietnamese", "vo": "Volapük", "wa": "Walloon",
    "xh": "Xhosa", "zh": "Chinese", "zu": "Zulu",
}


class UnsupportedLanguage(ValueError):
    """The text is in a language the library can't search. The message is shown to the user as is."""


@dataclass(frozen=True)
class Detection:
    lang: str | None   # ISO 639-1, None when undetermined
    confidence: float
    size: int          # UTF-8 bytes of the text identified, whitespace excluded


@lru_cache(maxsize=1)
def _identifier():
    from py3langid.langid import MODEL_FILE, LanguageIdentifier
    return LanguageIdentifier.from_pickled_model(MODEL_FILE, norm_probs=True)


def name(code: str) -> str:
    return NAMES.get(code, code)


def normalize(code: str | None) -> str | None:
    """A provider's code as a base ISO 639-1 code: "en-US" and "EN" → "en"."""
    if not code or not code.strip():
        return None
    return re.split(r"[-_]", code.strip())[0].lower()


def prose(text: str) -> str:
    """The text without code blocks, inline code, URLs, identifier-shaped tokens
    or symbol characters (Unicode category S), case folded."""
    for pattern in (_FENCED, _INLINE_CODE, _URL, _IDENTIFIER):
        text = pattern.sub(" ", text)
    return "".join(" " if unicodedata.category(c).startswith("S") else c for c in text).casefold()


def detect(text: str) -> Detection:
    cleaned = prose(text)
    size = len("".join(cleaned.split()).encode())
    if size < MIN_BYTES:
        return Detection(None, 0.0, size)
    lang, confidence = _identifier().classify(cleaned)
    return Detection(lang if confidence >= MIN_CONFIDENCE else None, float(confidence), size)


def resolve(text: str, reported: str | None = None) -> str | None:
    """The text's language: what the text itself says when that is determined,
    else the provider's reported code, else None."""
    detected = detect(text)
    reported = normalize(reported)
    if detected.lang and reported and detected.lang != reported:
        logger.info("language: provider reported %s, text detected as %s (%.2f, %d bytes)",
                    reported, detected.lang, detected.confidence, detected.size)
    return detected.lang or reported


def require_supported(text: str, reported: str | None = None) -> str | None:
    """The text's language (None when undetermined); raises UnsupportedLanguage
    when it is determined and not supported."""
    lang = resolve(text, reported)
    if lang is not None and lang not in SUPPORTED:
        raise UnsupportedLanguage(f"This looks like {name(lang)}. Contendo can only learn from English for now.")
    return lang
