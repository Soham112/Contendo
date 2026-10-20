"""Load the provenance test set (step 3.3). No backend imports, no side effects.

Two sources of cases, both labelled by reading each text:
    fixtures/quality_v1/personas/<slug>/sources/*.md   the retrieval fixtures (`authorship` header)
    fixtures/provenance_v1/<slug>/*.md                 hard cases for the classifier only, never seeded

provenance_v1 headers: title, input_type, source_type, title_origin, authorship,
split, tests (what the case checks), and optionally author and authorship_other
(1-based blank-line paragraphs with the other label). <slug> is a quality_v1
persona, whose profile, account and experience nodes are the user's details.

Split: every quality_v1 source is dev, and provenance_v1 cases say their own.
The first hold-out (tc's sources and 11 provenance_v1 cases) was read to diagnose
the 2026-10-19 baseline (evals/baselines/2026-10-19-provenance-v1.md), so it is
dev now; the hold-out is 12 cases written after that, before any run on them.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import quality_fixtures as qf
from loaders import EVALS_DIR, SOURCE_TYPES, FixtureError, parse_authorship, parse_header

PROVENANCE_DIR = EVALS_DIR / "fixtures" / "provenance_v1"
INPUT_TYPES = frozenset({"note", "file", "url", "youtube"})
TITLE_ORIGINS = frozenset({"provided", "derived"})
SPLITS = frozenset({"dev", "holdout"})
_REQUIRED = ("title", "input_type", "source_type", "title_origin", "authorship", "split", "tests")

# How each retrieval fixture's source_type arrives in the product.
_QUALITY_INPUT_TYPES = {"personal_note": "note", "note": "note", "saved_content": "note",
                        "article": "url", "youtube": "youtube"}


@dataclass(frozen=True)
class Case:
    id: str
    persona: str
    split: str
    origin: str                       # quality_v1 | provenance_v1
    title: str
    title_origin: str
    input_type: str
    source_type: str
    author: str | None
    authorship: str                   # the label covering most of the text
    authorship_other: tuple[int, ...]  # paragraphs with the other label
    content: str
    tests: str = ""


def _quality_cases() -> list[Case]:
    cases = []
    for slug in qf.SYNTHETIC_SLUGS:
        for source in qf.load_quality_persona(slug).sources:
            cases.append(Case(
                id=source.path.stem, persona=slug, split="dev",
                origin="quality_v1", title=source.title, title_origin="provided",
                input_type=_QUALITY_INPUT_TYPES[source.source_type], source_type=source.source_type,
                author=None, authorship=source.authorship, authorship_other=source.authorship_other,
                content=source.content))
    return cases


def _provenance_case(path: Path, persona: str) -> Case:
    header, content = parse_header(path)
    missing = [k for k in _REQUIRED if not header.get(k)]
    if missing or not content:
        raise FixtureError(f"{path}: missing {missing or 'body'}")
    for key, allowed in (("input_type", INPUT_TYPES), ("source_type", SOURCE_TYPES),
                         ("title_origin", TITLE_ORIGINS), ("split", SPLITS)):
        if header[key] not in allowed:
            raise FixtureError(f"{path}: {key} must be one of {sorted(allowed)}")
    authorship, other = parse_authorship(path, header)
    return Case(id=path.stem, persona=persona, split=header["split"], origin="provenance_v1",
                title=header["title"], title_origin=header["title_origin"], input_type=header["input_type"],
                source_type=header["source_type"], author=header.get("author") or None,
                authorship=authorship, authorship_other=other, content=content, tests=header["tests"])


def _provenance_cases() -> list[Case]:
    cases = []
    for root in sorted(p for p in PROVENANCE_DIR.iterdir() if p.is_dir()):
        if root.name not in qf.SYNTHETIC_SLUGS:
            raise FixtureError(f"{root}: not a quality_v1 persona")
        cases += [_provenance_case(p, root.name) for p in sorted(root.glob("*.md"))]
    return cases


def load_cases() -> list[Case]:
    cases = _quality_cases() + _provenance_cases()
    ids = [c.id for c in cases]
    if len(set(ids)) != len(ids):
        raise FixtureError("provenance case ids must be unique")
    return cases


def persona_details(slug: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    """(profile, account, experience nodes): what the backend's author_context_from reads."""
    persona = qf.load_quality_persona(slug)
    return persona.profile, qf.load_account(slug), persona.experience_nodes
