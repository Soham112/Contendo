"""Backfill `sources` (migration 014) in the eval project.

From the repo root, with the backend venv:
    backend/venv/bin/python evals/backfill_sources.py           # report only (read-only)
    backend/venv/bin/python evals/backfill_sources.py --apply   # insert the planned rows

The logic is backend/scripts/backfill_sources.py; this entry point loads the
eval environment behind the guard first, as every evals script does.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the planned rows (default: report only)")
    args = parser.parse_args(argv)

    from scripts.backfill_sources import run

    print(f"Eval project: {env.CONFIG.project_ref}")
    run(env.backend_client(), write=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
