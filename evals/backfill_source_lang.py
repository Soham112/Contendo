"""Report source languages and backfill `sources.lang` (migration 020) in the eval project.

From the repo root, with the backend venv:
    backend/venv/bin/python evals/backfill_source_lang.py           # report only (read-only)
    backend/venv/bin/python evals/backfill_source_lang.py --apply   # set sources.lang

The logic is backend/scripts/backfill_source_lang.py; this entry point loads the
eval environment behind the guard first, as every evals script does.
"""

import env  # noqa: F401  (must be the first project import)

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="set sources.lang (default: report only)")
    args = parser.parse_args(argv)

    from scripts.backfill_source_lang import run

    print(f"Eval project: {env.CONFIG.project_ref}")
    run(env.backend_client(), write=args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
