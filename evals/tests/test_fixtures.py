from collections import Counter

import pytest

from loaders import FixtureError, load_goldens, load_persona, load_users, parse_source, persona_slugs

PERSONAS = ("ds", "founder", "pm")


@pytest.fixture(scope="module")
def personas():
    return {slug: load_persona(slug) for slug in persona_slugs()}


def test_users_file_lists_exactly_the_personas():
    users = load_users(allow_placeholders=True)
    assert sorted(users) == sorted(PERSONAS) == persona_slugs()


def test_users_file_with_placeholders_is_refused_for_real_use():
    users = load_users(allow_placeholders=True)
    if all(v.startswith("REPLACE") for v in users.values()):
        with pytest.raises(FixtureError):
            load_users()


@pytest.mark.parametrize("slug", PERSONAS)
def test_persona_fixture_shape(personas, slug):
    p = personas[slug]
    assert 8 <= len(p.sources) <= 15
    assert 2 <= len(p.posts) <= 3
    assert p.experience_nodes
    lengths = sorted(len(s.content.split()) for s in p.sources)
    assert lengths[-1] >= 2 * lengths[0], "sources should vary in length"
    assert {s.memory_context for s in p.sources} >= {"work", "learning", "personal_project", "observation"}


def test_goldens_are_valid_and_balanced(personas):
    goldens = load_goldens(personas=personas)
    assert Counter(g["persona"] for g in goldens) == {slug: 9 for slug in PERSONAS}
    # One targeted golden per persona, aimed at a single external source. For pm and founder
    # the post should be "learned"; for ds retrieval also returns the persona's own notes ("mixed").
    assert {g["id"]: g["expected_perspective"] for g in goldens if "expected_perspective" in g} == {
        "ds-09": "mixed", "pm-09": "learned", "founder-09": "learned"}
    for slug in PERSONAS:
        difficulties = {g["difficulty"] for g in goldens if g["persona"] == slug}
        assert difficulties == {"rich", "sparse", "off_topic"}, slug


def test_golden_with_unknown_source_title_is_refused(tmp_path, personas):
    bad = tmp_path / "goldens.jsonl"
    bad.write_text(
        '{"id": "x", "persona": "ds", "difficulty": "sparse", "topic": "t", "context": "", '
        '"format": "linkedin post", "tone": "casual", "length": "standard", '
        '"expected_source_titles": ["No such source"]}\n'
    )
    with pytest.raises(FixtureError, match="No such source"):
        load_goldens(bad, personas=personas)


def test_source_without_memory_context_is_refused(tmp_path):
    src = tmp_path / "x.md"
    src.write_text("---\ntitle: X\nsource_type: note\n---\nbody\n")
    with pytest.raises(FixtureError, match="memory_context"):
        parse_source(src)
