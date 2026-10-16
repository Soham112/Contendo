"""Delete the eval personas' rows from the eval Supabase project.

From the repo root, with the backend venv:
    backend/venv/bin/python evals/reset.py                 # every eval persona
    backend/venv/bin/python evals/reset.py --persona ds    # one persona (slug or uuid)
    backend/venv/bin/python evals/reset.py --quality       # the quality_v1 personas instead

Only deletes rows whose user id is one of the uuids in fixtures/users.json (or
fixtures/quality_v1/users.json with --quality), in
every migration table that has a user id (guard.RESET_TABLES).
Auth users are kept. Refuses to start if the env guard fails, and asks you to
type the project ref before deleting.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import sys

from postgrest.types import ReturnMethod

from guard import RESET_TABLES, EnvGuardError, resolve_reset_targets
from loaders import FixtureError, load_users
from quality_fixtures import USERS_FILE as QUALITY_USERS_FILE


def count_rows(client, table: str, column: str, user_id: str) -> int:
    result = client.table(table).select(column, count="exact", head=True).eq(column, user_id).execute()
    return result.count or 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--persona", action="append", default=[], help="persona slug or uuid (repeatable); default: all")
    parser.add_argument("--quality", action="store_true", help="target the quality_v1 users instead")
    args = parser.parse_args(argv)

    try:
        users = load_users(QUALITY_USERS_FILE) if args.quality else load_users()
        targets = resolve_reset_targets(args.persona, users)
        client = env.backend_client()
    except (EnvGuardError, FixtureError) as exc:
        print(f"refusing to reset: {exc}", file=sys.stderr)
        return 2

    ref = env.CONFIG.project_ref
    print(f"Eval project: {ref}")
    counts: dict[tuple[str, str], int] = {}
    for slug, uid in targets.items():
        print(f"\n{slug} ({uid})")
        for table, column in RESET_TABLES:
            n = count_rows(client, table, column, uid)
            counts[(slug, table)] = n
            if n:
                print(f"  {table:<24} {n}")
    total = sum(counts.values())
    if total == 0:
        print("\nNothing to delete.")
        return 0

    answer = input(f"\nDelete {total} rows from {ref}? Type the project ref to confirm: ")
    if answer.strip() != ref:
        print("Aborted.")
        return 1

    from memory.source_store import delete_all_for_user

    for slug, uid in targets.items():
        # Stored originals live in Storage, not a table: remove them with their rows.
        delete_all_for_user(uid)
        for table, column in RESET_TABLES:
            if counts[(slug, table)]:
                client.table(table).delete(returning=ReturnMethod.minimal).eq(column, uid).execute()
        print(f"{slug}: deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
