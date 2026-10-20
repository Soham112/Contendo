"""Load and validate the quality_v1 test set. No backend imports, no side effects.

Layout (see goldens/quality_v1/README.md):
    fixtures/quality_v1/personas/<slug>/profile.json        profiles.data, or null (no profile row)
    fixtures/quality_v1/personas/<slug>/account.json        optional: the PUT /account/segment body
    fixtures/quality_v1/personas/<slug>/experience_nodes.json, posts.json
    fixtures/quality_v1/personas/<slug>/sources/*.md        may be empty
    fixtures/quality_v1/users.json                          slug -> eval auth user uuid
    goldens/quality_v1/cases.jsonl, sequences.json
    private/quality_v1/me_cases.jsonl, me/snapshot.json     persona `me` (gitignored)

Label ids: a source file's stem ("rf-s03"), "<slug>-bp" for a business's profile
note, "<case id>-details" for the note a case's pillar_details is saved as
(details_id, e.g. "re-02-details"), and "me:<prefix>" for `me`.
"""
import json
from pathlib import Path
from typing import Any

from guard import validate_users
from loaders import EVALS_DIR, FixtureError, Persona, _load_json_list, parse_source
from quality_metrics import BUSINESS_NOTE_SUFFIX  # noqa: F401  (re-exported: qf.BUSINESS_NOTE_SUFFIX)

QUALITY_DIR = EVALS_DIR / "fixtures" / "quality_v1"
PERSONAS_DIR = QUALITY_DIR / "personas"
USERS_FILE = QUALITY_DIR / "users.json"
GOLDENS_DIR = EVALS_DIR / "goldens" / "quality_v1"
CASES_FILE = GOLDENS_DIR / "cases.jsonl"
PRIVATE_DIR = EVALS_DIR / "private" / "quality_v1"
ME_CASES_FILE = PRIVATE_DIR / "me_cases.jsonl"
ME_SNAPSHOT_FILE = PRIVATE_DIR / "me" / "snapshot.json"
ME_EXPORT_FILE = PRIVATE_DIR / "me" / "export.json"

SYNTHETIC_SLUGS = ("rf", "tc", "ni0", "ni1", "re", "fs", "bo", "nb")
ME = "me"
DETAILS_SUFFIX = "-details"
# The memory contexts that make a fixture source the author's own experience.
OWN_CONTEXTS = frozenset({"work", "personal_project"})

# spec §8.1, plus the proposed business angle (docs/QUALITY.md "Where the spec and this bar disagree").
ANGLES = frozenset(
    "personal_story contrarian_opinion mistake_lesson confession unexpected_result observation how_to "
    "framework case_study before_after prediction myth_busting analysis list failure_to_realization "
    "changed_my_mind announcement".split()
)
CASE_FIELDS = (
    "id", "persona", "split", "identity", "topic", "context", "pillar", "pillar_details", "tone", "objective",
    "authority", "cold_start_tier", "phrasing", "coverage", "evidence", "must_use_all", "must_use_any",
    "background", "off_topic", "central_idea", "eligible_angles", "ineligible_angles", "needs_present",
    "needs_missing", "do_not_claim", "note", "label_confidence",
)
_ENUMS = {
    "split": {"dev", "holdout"}, "identity": {"person", "business"}, "authority": {"high", "low"},
    "cold_start_tier": {0, 1, 2, 3}, "phrasing": {"names_project", "vague", "broad"},
    "coverage": {"full", "partial", "none"}, "evidence": {"first_person", "outside_only", "business_facts", "none"},
    "label_confidence": {"verified", "metadata_only"},
}


def details_id(case_id: str) -> str:
    """Label id of the note a case's pillar_details is saved as."""
    return case_id + DETAILS_SUFFIX


def load_account(slug: str) -> dict[str, Any] | None:
    path = PERSONAS_DIR / slug / "account.json"
    if not path.exists():
        return None
    account = json.loads(path.read_text())
    if account.get("segment") not in ("individual", "business"):
        raise FixtureError(f"{path}: segment must be individual or business")
    if account["segment"] == "business" and not account.get("business_profile"):
        raise FixtureError(f"{path}: a business needs business_profile")
    return account


def is_business(slug: str) -> bool:
    account = load_account(slug)
    return bool(account and account["segment"] == "business")


def load_quality_persona(slug: str) -> Persona:
    """A synthetic persona. Unlike loaders.load_persona, a null profile and an
    empty library are allowed: they are the cold-start states under test."""
    root = PERSONAS_DIR / slug
    if not root.is_dir():
        raise FixtureError(f"no quality_v1 fixtures for persona {slug!r} at {root}")
    profile = json.loads((root / "profile.json").read_text())
    if profile is not None and (not isinstance(profile, dict) or not profile.get("name") or not profile.get("role")):
        raise FixtureError(f"{root / 'profile.json'}: null, or an object with at least name and role")
    sources = [parse_source(p) for p in sorted((root / "sources").glob("*.md"))]
    unlabelled = [s.path.name for s in sources if s.authorship is None]
    if unlabelled:
        raise FixtureError(f"{slug}: every source needs an authorship label: {unlabelled}")
    titles = [s.title for s in sources]
    if len(set(titles)) != len(titles):
        raise FixtureError(f"{slug}: source titles must be unique")
    posts = _load_json_list(root / "posts.json")
    if len({p["topic"] for p in posts}) != len(posts):
        raise FixtureError(f"{slug}: seed post topics must be unique (seed.py matches on topic)")
    return Persona(slug, profile, _load_json_list(root / "experience_nodes.json"), posts, sources)


def source_labels(slug: str) -> dict[str, str]:
    """label id -> source title, for a synthetic persona's fixture sources."""
    return {s.path.stem: s.title for s in load_quality_persona(slug).sources}


def own_label_ids(slug: str) -> frozenset[str]:
    """Label ids that are the author's own experience (criterion 3), by fixture
    memory_context; a business's profile and details notes are its own words."""
    own = {s.path.stem for s in load_quality_persona(slug).sources if s.memory_context in OWN_CONTEXTS}
    if is_business(slug):
        own.add(slug + BUSINESS_NOTE_SUFFIX)
    own |= {details_id(c["id"]) for c in _read_jsonl(CASES_FILE) if c["persona"] == slug and c.get("pillar_details")}
    return frozenset(own)


def load_snapshot() -> dict[str, Any]:
    if not ME_SNAPSHOT_FILE.exists():
        raise FixtureError(f"{ME_SNAPSHOT_FILE} is missing (persona `me` lives only on Soham's machine)")
    return json.loads(ME_SNAPSHOT_FILE.read_text())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _case_errors(case: dict[str, Any], known: set[str]) -> list[str]:
    cid = case.get("id", "?")
    errs = [f"{cid}: missing {f}" for f in CASE_FIELDS if f not in case]
    if errs:
        return errs
    errs += [f"{cid}: {k}={case[k]!r}" for k, allowed in _ENUMS.items() if case[k] not in allowed]
    refs = case["must_use_all"] + case["must_use_any"] + case["background"] + case["off_topic"]
    refs += [n["source"] for n in case["needs_present"]]
    errs += [f"{cid}: unknown source {r}" for r in refs if r not in known]
    angles = case["eligible_angles"] + [x["angle"] for x in case["ineligible_angles"]]
    errs += [f"{cid}: unknown angle {a}" for a in angles if a not in ANGLES]
    required = set(case["must_use_all"]) | set(case["must_use_any"])
    if required & (set(case["background"]) | set(case["off_topic"])):
        errs.append(f"{cid}: a required source is also background or off_topic")
    if set(case["must_use_all"]) & set(case["must_use_any"]):
        errs.append(f"{cid}: a source is in both must_use_all and must_use_any")
    if len(case["must_use_any"]) == 1:
        errs.append(f"{cid}: must_use_any needs two or more sources (one belongs in must_use_all)")
    if set(case["eligible_angles"]) & {x["angle"] for x in case["ineligible_angles"]}:
        errs.append(f"{cid}: an angle is both eligible and ineligible")
    if (case["persona"] == ME) != (case["label_confidence"] == "metadata_only"):
        errs.append(f"{cid}: only persona me is metadata_only")
    # Business posts get the profile note as a fixed block in the prompt, not
    # through retrieval: business cases say so, and never require the note.
    business = case["persona"] != ME and is_business(case["persona"])
    if bool(case.get("business_block")) != business:
        errs.append(f"{cid}: business_block must be true exactly for business personas")
    if business and case.get("expected_gate") not in {"pass", "profile_only", "low_coverage"}:
        errs.append(f"{cid}: every business case requires expected_gate (pass, profile_only or low_coverage)")
    if business and case["persona"] + BUSINESS_NOTE_SUFFIX in required:
        errs.append(f"{cid}: the profile note reaches business posts as a block, not a required source")
    return errs


def load_cases(include_private: bool = True) -> list[dict[str, Any]]:
    """Every case, validated against the fixtures. Persona `me` is included when
    its private files exist on this machine and include_private is set."""
    cases = _read_jsonl(CASES_FILE)
    me_known: set[str] = set()
    if include_private and ME_CASES_FILE.exists():
        cases += _read_jsonl(ME_CASES_FILE)
        me_known = {f"me:{k}" for k in load_snapshot()["labelled_sources"]}
    known_by_persona: dict[str, set[str]] = {ME: me_known}
    for slug in SYNTHETIC_SLUGS:
        known = set(source_labels(slug))
        if is_business(slug):
            known.add(slug + BUSINESS_NOTE_SUFFIX)
        known_by_persona[slug] = known
    errs: list[str] = []
    ids = [c.get("id") for c in cases]
    if len(set(ids)) != len(ids):
        errs.append("duplicate case ids")
    for case in cases:
        if case.get("persona") not in known_by_persona:
            errs.append(f"{case.get('id')}: unknown persona {case.get('persona')!r}")
            continue
        known = known_by_persona[case["persona"]] | ({details_id(case["id"])} if case.get("pillar_details") else set())
        errs += _case_errors(case, known)
    if errs:
        raise FixtureError("quality_v1 cases:\n  " + "\n  ".join(errs))
    return cases


def user_slug(case: dict[str, Any]) -> str:
    """The eval user a case runs as. A case with pillar_details gets its own user,
    seeded as its persona plus that note (as /generate would have saved it), so
    scoring never writes to a library other cases read."""
    return case["id"] if case["pillar_details"] else case["persona"]


def details_states() -> dict[str, dict[str, Any]]:
    """user slug -> case, for every public case that carries pillar_details."""
    return {c["id"]: c for c in _read_jsonl(CASES_FILE) if c.get("pillar_details")}


def load_quality_users(allow_missing: bool = False) -> dict[str, str]:
    """users.json for quality_v1 (slug -> uuid). Missing slugs are an error unless allowed."""
    raw = json.loads(USERS_FILE.read_text()) if USERS_FILE.exists() else {}
    users = validate_users(raw) if raw else {}
    missing = [s for s in (*SYNTHETIC_SLUGS, *details_states(), ME) if s not in users]
    if missing and not allow_missing:
        raise FixtureError(f"{USERS_FILE}: no eval user for {missing}; run quality_seed.py --create-users")
    return users
