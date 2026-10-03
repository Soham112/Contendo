"""Seed the eval personas into the eval Supabase project. Safe to re-run.

From the repo root, with the backend venv:
    backend/venv/bin/python evals/seed.py --check        # validate everything, write nothing
    backend/venv/bin/python evals/seed.py                # seed every persona (asks first)
    backend/venv/bin/python evals/seed.py --persona ds --yes

Before any write it checks the env guard, the fixtures and goldens, and that every
target uuid exists in the eval project's auth.users. Re-running only spends API
credits on sources whose text changed: ingest_content skips content it has seen.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import sys
import uuid
from typing import Any

from guard import EnvGuardError
from loaders import FixtureError, Persona, load_goldens, load_persona, load_users, persona_slugs

# Namespace for deterministic experience_ids, so re-seeding keeps the same ids.
_EXPERIENCE_NS = uuid.UUID("6f1d2c1e-7a54-4f0b-9a7e-3c2f8e5d9b10")


def _experience_id(slug: str, node: dict[str, Any]) -> str:
    key = f"{slug}:{node['node_type']}:{node['entity_name']}:{node.get('role') or ''}"
    return str(uuid.uuid5(_EXPERIENCE_NS, key))


def seed_persona(persona: Persona, user_id: str, client: Any) -> str:
    """Write one persona's profile, experience nodes, sources and posts. Returns a summary line."""
    from agents.ingestion_agent import ingest_content
    from memory.experience_store import save_experience_nodes
    from memory.feedback_store import log_post
    from memory.profile_store import save_profile

    slug = persona.slug
    save_profile(persona.profile, user_id=user_id)

    nodes = [{**n, "experience_id": n.get("experience_id") or _experience_id(slug, n)} for n in persona.experience_nodes]
    save_experience_nodes(user_id, nodes)

    ingested = duplicate = 0
    for source in persona.sources:
        result = ingest_content(
            source.content,
            source_type=source.source_type,
            source_title=source.title,
            user_id=user_id,
            memory_context=source.memory_context,
        )
        if result.get("duplicate"):
            duplicate += 1
            print(f"  [{slug}] duplicate  {source.title}")
        else:
            ingested += 1
            print(f"  [{slug}] ingested   {source.title} ({result.get('chunks_stored', 0)} chunks)")

    rows = client.table("posts").select("topic").eq("user_id", user_id).execute().data or []
    existing_topics = {r["topic"] for r in rows}
    added = 0
    for post in persona.posts:
        if post["topic"] in existing_topics:
            continue
        log_post(
            topic=post["topic"],
            format=post["format"],
            tone=post["tone"],
            content=post["content"],
            authenticity_score=int(post.get("authenticity_score", 0)),
            archetype=post.get("archetype", ""),
            user_id=user_id,
        )
        added += 1

    # Sources in the DB that the fixtures no longer have (edited or removed files).
    rows = (
        client.table("embeddings").select("source_title,node_type").eq("user_id", user_id).execute().data or []
    )
    fixture_titles = {s.title for s in persona.sources}
    stale = sorted({
        r["source_title"] for r in rows
        if (r.get("node_type") or "chunk") == "chunk" and r["source_title"] not in fixture_titles
    })
    if stale:
        print(f"  [{slug}] WARNING: {len(stale)} source(s) in the DB are not in the fixtures: {stale}. "
              f"Run reset.py --persona {slug}, then seed again.")

    return (
        f"{slug}: profile ok · {len(nodes)} experience nodes · "
        f"{len(persona.sources)} sources ({ingested} ingested, {duplicate} duplicate) · "
        f"{len(persona.posts)} posts ({added} added, {len(persona.posts) - added} existing)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--persona", action="append", help="persona slug (repeatable); default: all")
    parser.add_argument("--check", action="store_true", help="validate fixtures, goldens and auth users; write nothing")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args(argv)

    try:
        users = load_users()
        all_slugs = persona_slugs()
        missing_users = [s for s in all_slugs if s not in users]
        if missing_users:
            raise FixtureError(f"personas without a uuid in users.json: {missing_users}")
        slugs = args.persona or all_slugs
        unknown = [s for s in slugs if s not in all_slugs or s not in users]
        if unknown:
            raise FixtureError(f"unknown persona(s): {unknown}; known: {all_slugs}")

        personas = {s: load_persona(s) for s in all_slugs}
        goldens = load_goldens(personas=personas)
        targets = {s: users[s] for s in slugs}
        env.verify_auth_users(targets)
        env.verify_anthropic_key()
        client = env.backend_client()
    except (EnvGuardError, FixtureError) as exc:
        print(f"refusing to seed: {exc}", file=sys.stderr)
        return 2

    print(f"Eval project: {env.CONFIG.project_ref}")
    print(f"Fixtures ok: {len(personas)} personas, {len(goldens)} goldens. Auth users ok: {', '.join(slugs)}. "
          "Anthropic key ok.")
    for slug in slugs:
        p = personas[slug]
        print(f"  {slug}: {len(p.sources)} sources, {len(p.experience_nodes)} experience nodes, {len(p.posts)} posts")
    if args.check:
        print("Check only: nothing written.")
        return 0

    if not args.yes:
        answer = input(f"Seed {len(slugs)} persona(s) into {env.CONFIG.project_ref}? "
                       "New sources call Claude (~$0.01-0.03 each). [y/N] ")
        if answer.strip().lower() != "y":
            print("Aborted.")
            return 1

    summaries = [seed_persona(personas[slug], targets[slug], client) for slug in slugs]
    print()
    for line in summaries:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
