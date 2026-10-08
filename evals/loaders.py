"""Load and validate eval fixtures and goldens. No backend imports, no side effects.

Layout:
    fixtures/users.json                       persona slug -> auth user uuid
    fixtures/personas/<slug>/profile.json     profiles.data for the persona
    fixtures/personas/<slug>/experience_nodes.json
    fixtures/personas/<slug>/posts.json       seed posts (so first_post is False)
    fixtures/personas/<slug>/sources/*.md     knowledge base, one source per file
    goldens/goldens.jsonl                     one golden per line

A source file starts with a header block, then the body that gets ingested:

    ---
    title: Kestrel holiday forecast postmortem
    source_type: personal_note
    memory_context: work
    ---
    Body text...
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from guard import USERS_FILE, EnvGuardError, validate_users

EVALS_DIR = Path(__file__).resolve().parent
PERSONAS_DIR = EVALS_DIR / "fixtures" / "personas"
GOLDENS_FILE = EVALS_DIR / "goldens" / "goldens.jsonl"

# Values the backend accepts (routers/ingest.py, agents/ingestion_agent.py,
# memory/experience_store.py, utils/formatters.py, agents/draft_agent.py).
SOURCE_TYPES = {"article", "youtube", "note", "personal_note", "saved_content"}
MEMORY_CONTEXTS = {"work", "personal_project", "learning", "observation"}
NODE_TYPES = {"work", "personal_project", "education"}
FORMATS = {"linkedin post", "medium article", "thread"}
TONES = {"casual", "technical", "storytelling"}
LENGTHS = {"concise", "standard", "long-form"}
ARCHETYPES = {
    "incident_report", "contrarian_take", "personal_story", "teach_me_something",
    "list_that_isnt", "prediction_bet", "before_after", "general",
}
DIFFICULTIES = {"rich", "sparse", "off_topic"}
GOLDEN_FIELDS = (
    "id", "persona", "topic", "context", "format", "tone", "length",
    "expected_source_titles", "difficulty",
)
# Optional: the perspective the pipeline should decide for this golden
# (generation_traces.node_outputs.perspective). Targeted goldens set it.
# `note`: a free-text comment explaining the golden (JSONL has no comments).
OPTIONAL_GOLDEN_FIELDS = ("expected_perspective", "note")
PERSPECTIVES = {"experience", "learned", "opinion", "mixed"}


class FixtureError(ValueError):
    """A fixture or golden file is malformed."""


@dataclass(frozen=True)
class Source:
    title: str
    source_type: str
    memory_context: str
    content: str
    path: Path


@dataclass(frozen=True)
class Persona:
    slug: str
    profile: dict[str, Any]
    experience_nodes: list[dict[str, Any]]
    posts: list[dict[str, Any]]
    sources: list[Source]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def load_users(path: Path = USERS_FILE, *, allow_placeholders: bool = False) -> dict[str, str]:
    """users.json as {slug: uuid}. Placeholders are only allowed when asked (shape checks)."""
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict) or not all(isinstance(v, str) for v in raw.values()):
        raise FixtureError(f"{path}: expected an object of persona slug -> uuid string")
    if allow_placeholders:
        return dict(raw)
    try:
        return validate_users(raw)
    except EnvGuardError as exc:
        raise FixtureError(f"{path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

def parse_source(path: Path) -> Source:
    text = path.read_text()
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FixtureError(f"{path}: must start with a '---' header block")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise FixtureError(f"{path}: header block is not closed with '---'")
    header: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise FixtureError(f"{path}: header line {line!r} is not 'key: value'")
        header[key.strip()] = value.strip()
    content = "\n".join(lines[end + 1:]).strip()

    for key in ("title", "source_type", "memory_context"):
        if not header.get(key):
            raise FixtureError(f"{path}: header is missing {key}")
    if header["source_type"] not in SOURCE_TYPES:
        raise FixtureError(f"{path}: source_type must be one of {sorted(SOURCE_TYPES)}")
    if header["memory_context"] not in MEMORY_CONTEXTS:
        raise FixtureError(f"{path}: memory_context must be one of {sorted(MEMORY_CONTEXTS)}")
    if not content:
        raise FixtureError(f"{path}: body is empty")
    return Source(header["title"], header["source_type"], header["memory_context"], content, path)


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
        raise FixtureError(f"{path}: expected a list of objects")
    return data


def load_persona(slug: str, personas_dir: Path = PERSONAS_DIR) -> Persona:
    root = personas_dir / slug
    if not root.is_dir():
        raise FixtureError(f"no fixtures for persona {slug!r} at {root}")

    profile = json.loads((root / "profile.json").read_text())
    if not isinstance(profile, dict) or not profile.get("name") or not profile.get("role"):
        raise FixtureError(f"{root / 'profile.json'}: needs at least name and role")

    nodes = _load_json_list(root / "experience_nodes.json")
    for node in nodes:
        if node.get("node_type") not in NODE_TYPES or not node.get("entity_name"):
            raise FixtureError(f"{slug} experience node {node!r}: needs node_type in {sorted(NODE_TYPES)} and entity_name")

    posts = _load_json_list(root / "posts.json")
    for post in posts:
        for key in ("topic", "format", "tone", "content"):
            if not post.get(key):
                raise FixtureError(f"{slug} seed post is missing {key}: {post!r}")
        if post["format"] not in FORMATS or post["tone"] not in TONES:
            raise FixtureError(f"{slug} seed post {post['topic']!r}: bad format or tone")
        if post.get("archetype", "") and post["archetype"] not in ARCHETYPES:
            raise FixtureError(f"{slug} seed post {post['topic']!r}: unknown archetype")
    if len({p["topic"] for p in posts}) != len(posts):
        raise FixtureError(f"{slug}: seed post topics must be unique (seed.py matches on topic)")

    sources = [parse_source(p) for p in sorted((root / "sources").glob("*.md"))]
    if not sources:
        raise FixtureError(f"{slug}: no sources in {root / 'sources'}")
    titles = [s.title for s in sources]
    if len(set(titles)) != len(titles):
        raise FixtureError(f"{slug}: source titles must be unique")

    return Persona(slug, profile, nodes, posts, sources)


def persona_slugs(personas_dir: Path = PERSONAS_DIR) -> list[str]:
    return sorted(p.name for p in personas_dir.iterdir() if p.is_dir())


# ---------------------------------------------------------------------------
# Goldens
# ---------------------------------------------------------------------------

def load_goldens(
    path: Path = GOLDENS_FILE, personas: dict[str, Persona] | None = None
) -> list[dict[str, Any]]:
    """Every golden, validated. With personas, expected_source_titles are checked too."""
    goldens: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path.name}:{lineno}"
        try:
            g = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FixtureError(f"{where}: invalid JSON: {exc}") from exc
        missing = [f for f in GOLDEN_FIELDS if f not in g]
        if missing:
            raise FixtureError(f"{where}: missing {', '.join(missing)}")
        extra = sorted(set(g) - set(GOLDEN_FIELDS) - set(OPTIONAL_GOLDEN_FIELDS))
        if extra:
            raise FixtureError(f"{where}: unknown fields {', '.join(extra)}")
        if g["id"] in seen:
            raise FixtureError(f"{where}: duplicate id {g['id']!r}")
        seen.add(g["id"])
        if not str(g["topic"]).strip():
            raise FixtureError(f"{where}: topic is empty")
        for field, allowed in (("format", FORMATS), ("tone", TONES), ("length", LENGTHS), ("difficulty", DIFFICULTIES)):
            if g[field] not in allowed:
                raise FixtureError(f"{where}: {field} {g[field]!r} not in {sorted(allowed)}")
        if g.get("expected_perspective", "learned") not in PERSPECTIVES:
            raise FixtureError(f"{where}: expected_perspective {g['expected_perspective']!r} not in {sorted(PERSPECTIVES)}")
        titles = g["expected_source_titles"]
        if not isinstance(titles, list):
            raise FixtureError(f"{where}: expected_source_titles must be a list")
        if g["difficulty"] == "off_topic" and titles:
            raise FixtureError(f"{where}: off_topic goldens expect no sources")
        if g["difficulty"] == "rich" and len(titles) < 2:
            raise FixtureError(f"{where}: rich goldens expect at least 2 sources")
        if g["difficulty"] == "sparse" and len(titles) > 1:
            raise FixtureError(f"{where}: sparse goldens expect at most 1 source")
        if personas is not None:
            if g["persona"] not in personas:
                raise FixtureError(f"{where}: unknown persona {g['persona']!r}")
            known = {s.title for s in personas[g["persona"]].sources}
            unknown = [t for t in titles if t not in known]
            if unknown:
                raise FixtureError(f"{where}: no {g['persona']} source titled {unknown}")
        goldens.append(g)
    return goldens
