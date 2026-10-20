"""Classify the authorship of existing sources (provenance step 3.3) in the eval project.

From the repo root, with the backend venv:
    backend/venv/bin/python evals/backfill_authorship.py                          # estimate only: $0
    backend/venv/bin/python evals/backfill_authorship.py --apply [--spend-cap 2.00]   # PAID, asks first

The logic is backend/scripts/backfill_authorship.py; this entry point loads the
eval environment behind the guard first, as every evals script does.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    from scripts.backfill_authorship import add_arguments, confirmer, run

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_arguments(parser)
    args = parser.parse_args(argv)

    print(f"Eval project: {env.CONFIG.project_ref}")
    return run(env.backend_client(), write=args.apply, cap_usd=args.spend_cap, confirm=confirmer(args.yes))


if __name__ == "__main__":
    sys.exit(main())
