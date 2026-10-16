"""Seed the quality_v1 personas into the eval Supabase project. Safe to re-run.

From the repo root, with the backend venv:
    backend/venv/bin/python evals/quality_seed.py --check           # validate; writes nothing
    backend/venv/bin/python evals/quality_seed.py --estimate        # expected Claude cost; writes nothing
    backend/venv/bin/python evals/quality_seed.py --create-users     # one eval auth user per persona
    backend/venv/bin/python evals/quality_seed.py                   # seed every synthetic persona (asks first)
    backend/venv/bin/python evals/quality_seed.py --persona me      # load private/.../export.json (no Claude calls)

Synthetic personas go through the same code real users do: the account is saved
the way PUT /account/segment saves it (so a business's profile note is built by
utils.business_notes.profile_note and ingested), then seed.seed_persona adds the
profile, experience nodes, sources and posts. Seeding stops before the next
persona once measured spend reaches --spend-cap.
"""
import env  # noqa: F401  (must be the first project import)

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

import quality_fixtures as qf
from guard import EnvGuardError
from loaders import FixtureError
from seed import seed_persona

EMAIL = "quality-{slug}@contendo-eval.invalid"
DEFAULT_SPEND_CAP_USD = 1.00
_BATCH = 100

# Ingestion calls per new source (agents/ingestion_agent.py, consolidation_agent.py):
# (event, model, prompt tokens besides the text, text tokens counted, typical output, max_tokens).
# Typical outputs are production medians (usage_events, 2026-10-15); max_tokens from the code.
_CALLS = (
    ("ingest_tags", "SONNET", 170, "document", 30, 150),
    ("ingest_entities", "HAIKU", 450, "chunk", 160, 300),
    ("ingest_summary", "HAIKU", 80, "document", 70, 120),
)
_CONSOLIDATION = ("HAIKU", 1_500, 150, 300)  # (model, input, typical output, max_tokens) per call
_TOKENS_PER_WORD = 1.35


def _tokens(words: int) -> int:
    return int(words * _TOKENS_PER_WORD)


def _persona_of(slug: str) -> str:
    """The fixture persona behind a user slug (a details state is its case's persona)."""
    return qf.details_states()[slug]["persona"] if slug in qf.details_states() else slug


def _source_texts(slug: str) -> list[str]:
    persona = _persona_of(slug)
    texts = [s.content for s in qf.load_quality_persona(persona).sources]
    if slug in qf.details_states():
        texts.append(qf.details_states()[slug]["pillar_details"])
    account = qf.load_account(persona)
    if account and account["segment"] == "business":
        texts.append(" ".join(str(v) for v in account["business_profile"].values()))  # the profile note
    return texts


def estimate(slugs: list[str]) -> tuple[float, float]:
    """(expected, upper bound) USD to ingest these personas' sources from empty."""
    from llm import client as llm
    from llm.pricing import call_cost

    expected = upper = 0.0
    for slug in slugs:
        texts = _source_texts(slug)
        for text in texts:
            words = len(text.split())
            for _event, model, overhead, _, typical, cap in _CALLS:
                tokens_in = overhead + _tokens(min(words, 1500))
                expected += call_cost(getattr(llm, model), tokens_in, typical)
                upper += call_cost(getattr(llm, model), tokens_in, cap)
        # Consolidation re-runs for every source that touches an entity already in 3+ sources.
        # Upper bound: every source after the second touches 3 such entities.
        model, tokens_in, typical, cap = _CONSOLIDATION
        later = max(0, len(texts) - 2)
        expected += later * call_cost(getattr(llm, model), tokens_in, typical)
        upper += later * 3 * call_cost(getattr(llm, model), tokens_in, cap)
    return expected, upper


class UsageLog:
    """Usage logging for a script, as the server has it: complete() hands each
    usage_events write to the main event loop (memory.usage_store), and a script
    has none, so without this every call goes unlogged and spend reads as zero.
    Runs a loop on a background thread, registers it, and measures spend from
    the rows written since it started."""

    def __enter__(self) -> "UsageLog":
        import asyncio
        import threading
        from memory import usage_store
        self._asyncio, self._store = asyncio, usage_store
        self.since = datetime.now(timezone.utc).isoformat()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        while not self.loop.is_running():
            threading.Event().wait(0.01)
        usage_store.set_main_loop(self.loop)
        return self

    def drain(self) -> None:
        """Wait until every usage write scheduled so far has finished."""
        asyncio = self._asyncio

        async def pending_done() -> None:
            while tasks := [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]:
                await asyncio.gather(*tasks, return_exceptions=True)
        asyncio.run_coroutine_threadsafe(pending_done(), self.loop).result(timeout=120)

    def spend(self, client: Any, user_ids: list[str]) -> float:
        """USD of the Claude calls these users made since this log started."""
        from llm.pricing import call_cost
        self.drain()
        rows = (client.table("usage_events").select("model,input_tokens,output_tokens")
                .in_("user_id", user_ids).gte("created_at", self.since).execute().data or [])
        return sum(call_cost(r["model"], r["input_tokens"] or 0, r["output_tokens"] or 0) for r in rows if r.get("model"))

    def __exit__(self, *exc: Any) -> None:
        self.drain()
        self._store.set_main_loop(None)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
        self.loop.close()


def check_spend_tracking(client: Any) -> None:
    """Refuse unless usage_events records the model of each call: the spend cap
    prices calls from it, so without it the cap can't see any spend."""
    try:
        client.table("usage_events").select("model").limit(1).execute()
    except Exception as exc:
        raise EnvGuardError(
            "the eval project's usage_events has no model column, so spend can't be measured: "
            "apply backend/migrations/006_add_usage_model.sql to the eval project"
        ) from exc


def details_note_for(case: dict[str, Any], user_id: str) -> tuple[str, str]:
    """(title, text) of the note /generate saves for this case's pillar_details."""
    from memory.account_store import get_account
    from utils.business_notes import details_note, find_pillar
    pillar = find_pillar(get_account(user_id), case["pillar"])
    if pillar is None:
        raise FixtureError(f"{case['id']}: pillar {case['pillar']!r} is not in the account's niche")
    return details_note(pillar, case["pillar_details"])


def seed_user(slug: str, user_id: str, client: Any) -> str:
    """Seed one user: its persona's account and fixtures, and for a details state
    the case's pillar_details note, saved as routers/generate.py run_generation saves it."""
    from agents.ingestion_agent import ingest_content
    persona = _persona_of(slug)
    extra = _seed_account(persona, user_id, client)
    case = qf.details_states().get(slug)
    if case:
        title, note = details_note_for(case, user_id)
        ingest_content(note, source_type="personal_note", source_title=title, user_id=user_id, memory_context="work")
        extra |= {title}
    summary = seed_persona(qf.load_quality_persona(persona), user_id, client, extra_titles=extra)
    return f"{slug} · {title} · {summary}" if case else summary


def create_users(client: Any) -> dict[str, str]:
    users = qf.load_quality_users(allow_missing=True)
    for slug in (*qf.SYNTHETIC_SLUGS, *qf.details_states(), qf.ME):
        if slug in users:
            continue
        created = client.auth.admin.create_user({"email": EMAIL.format(slug=slug), "email_confirm": True})
        users[slug] = created.user.id
        print(f"  created {slug}: {created.user.id}")
    qf.USERS_FILE.write_text(json.dumps(users, indent=2) + "\n")
    return users


def _seed_account(slug: str, user_id: str, client: Any) -> frozenset[str]:
    """Save the account as PUT /account/segment does. Returns the titles of the
    sources it created. Skipped when the stored account already matches, so a
    re-run doesn't pay to rebuild the profile note."""
    from memory.account_store import get_account, save_segment
    from routers.account import SegmentRequest, _ensure_voice_profile, _save_profile_to_memory
    from utils.business_notes import PROFILE_NOTE_TITLE

    account = qf.load_account(slug)
    if account is None:
        return frozenset()
    req = SegmentRequest(**account)  # the endpoint's own validation
    profile = req.business_profile.model_dump(mode="json") if req.business_profile else None
    business = req.segment == "business"
    stored = get_account(user_id)
    note = (client.table("embeddings").select("id").eq("user_id", user_id)
            .eq("source_title", PROFILE_NOTE_TITLE).limit(1).execute().data)
    if stored.get("segment") == req.segment and stored.get("business_profile") == profile and (note or not business):
        return frozenset({PROFILE_NOTE_TITLE}) if business else frozenset()
    saved = save_segment(user_id, req.segment, business_niche=req.business_niche,
                         business_niche_other=req.business_niche_other, business_profile=profile)
    if not business:
        return frozenset()
    _ensure_voice_profile(saved, user_id)
    _save_profile_to_memory(saved, user_id)
    return frozenset({PROFILE_NOTE_TITLE})


def import_me(user_id: str, client: Any) -> str:
    """Load the production export into the eval user `me`, rows as they are."""
    export = json.loads(qf.ME_EXPORT_FILE.read_text())
    t = export["tables"]
    keyed = (("embeddings", "user_id", "id"), ("entities", "user_id", "entity_id"),
             ("chunk_entities", "user_id", "chunk_id,entity_id"), ("experience_nodes", "user_id", "experience_id"),
             ("accounts", "user_id", "user_id"))
    for table, user_col, conflict in keyed:
        rows = [{**r, user_col: user_id} for r in t[table]]
        for i in range(0, len(rows), _BATCH):
            client.table(table).upsert(rows[i:i + _BATCH], on_conflict=conflict).execute()
    for row in t["profiles"]:
        client.table("profiles").upsert({"id": user_id, "data": row["data"]}).execute()
    existing = {r["topic"] for r in client.table("posts").select("topic").eq("user_id", user_id).execute().data or []}
    posts = [{**p, "user_id": user_id} for p in t["posts"] if p["topic"] not in existing]
    if posts:
        client.table("posts").insert(posts).execute()
    return f"me: {export['provenance']} · " + ", ".join(f"{k} {v}" for k, v in export["counts"].items())


def _confirm(prompt: str, yes: bool) -> bool:
    return yes or input(prompt).strip().lower() == "y"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--persona", action="append",
                        help="user slug (repeatable): a persona, a pillar_details case id, or me; default: all but me")
    parser.add_argument("--check", action="store_true", help="validate fixtures and users; write nothing")
    parser.add_argument("--estimate", action="store_true", help="print the expected Claude cost; write nothing")
    parser.add_argument("--create-users", action="store_true", help="create missing eval auth users")
    parser.add_argument("--spend-cap", type=float, default=DEFAULT_SPEND_CAP_USD, help="stop at this measured USD")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args(argv)
    seedable = (*qf.SYNTHETIC_SLUGS, *qf.details_states())
    slugs = args.persona or list(seedable)
    try:
        unknown = [s for s in slugs if s not in (*seedable, qf.ME)]
        if unknown:
            raise FixtureError(f"unknown persona(s): {unknown}")
        cases = qf.load_cases()
        client = env.backend_client()
        if args.create_users:
            if not _confirm(f"Create missing eval auth users in {env.CONFIG.project_ref}? [y/N] ", args.yes):
                return 1
            create_users(client)
        users = qf.load_quality_users(allow_missing=args.check or args.estimate)
        if qf.ME in slugs and not qf.ME_EXPORT_FILE.exists():
            raise FixtureError(f"{qf.ME_EXPORT_FILE} is missing: run quality_export_me.py first")
        env.verify_auth_users({s: users[s] for s in slugs if s in users})
        check_spend_tracking(client)
    except (EnvGuardError, FixtureError) as exc:
        print(f"refusing to seed: {exc}", file=sys.stderr)
        return 2
    synthetic = [s for s in slugs if s != qf.ME]
    expected, upper = estimate(synthetic)
    print(f"Eval project: {env.CONFIG.project_ref}. Cases ok: {len(cases)}. Users: {len(users)}.")
    print(f"Claude cost to ingest {', '.join(synthetic) or 'nothing'} from empty: expected ${expected:.2f}, "
          f"upper bound ${upper:.2f}; cap ${args.spend_cap:.2f}. Sources already stored cost nothing.")
    if args.check or args.estimate:
        return 0
    if not _confirm(f"Seed {', '.join(slugs)} into {env.CONFIG.project_ref}? [y/N] ", args.yes):
        print("Aborted.")
        return 1
    env.verify_anthropic_key()
    with UsageLog() as usage:
        for slug in slugs:
            if slug == qf.ME:
                print(import_me(users[slug], client))
                continue
            spent = usage.spend(client, list(users.values()))
            if spent >= args.spend_cap:
                print(f"Spend cap reached (${spent:.2f}): stopped before {slug}.")
                return 3
            print(seed_user(slug, users[slug], client))
        print(f"Measured Claude spend: ${usage.spend(client, list(users.values())):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
