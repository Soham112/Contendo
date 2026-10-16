"""Report the language of every existing source, and backfill `sources.lang` (migration 020).

Each source's extracted_text is identified with utils.language.detect, the check
new ingests go through. $0: local, no model calls.

Production, from backend/ (reads backend/.env):
    venv/bin/python -m scripts.backfill_source_lang                                # report only (read-only)
    venv/bin/python -m scripts.backfill_source_lang --apply --confirm-production
Eval, from the repo root, through the evals env guard:
    backend/venv/bin/python evals/backfill_source_lang.py [--apply]

The report counts sources per detected language, overall and per user (first 8
characters of the id), and lists the sources not in a supported language (user,
source id, input type, language, size) so their owners can be told. Ids only, no
titles or text. --apply sets `lang` where it is NULL and the language is
determined; undetermined text stays NULL, as on new ingests. Re-running is safe.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.language import SUPPORTED, detect

PAGE = 1000  # PostgREST's maximum rows per request
UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class Identified:
    user_id: str
    source_id: str
    input_type: str
    lang: str | None      # detected; None when undetermined
    size: int
    stored_lang: str | None


def fetch_sources(client: Any, *, with_lang: bool) -> list[dict]:
    """Every source row, paged past the 1,000-row response limit. `lang` is read
    only when asked: before migration 020 the column doesn't exist."""
    columns = "source_id,user_id,input_type,extracted_text" + (",lang" if with_lang else "")
    rows: list[dict] = []
    while True:
        page = (client.table("sources").select(columns).order("source_id")
                .range(len(rows), len(rows) + PAGE - 1).execute().data or [])
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def identify(rows: list[dict]) -> list[Identified]:
    out = []
    for r in rows:
        d = detect(r.get("extracted_text") or "")
        out.append(Identified(r["user_id"], r["source_id"], r.get("input_type") or "", d.lang, d.size,
                              r.get("lang")))
    return out


def report(found: list[Identified]) -> str:
    def label(i: Identified) -> str:
        return i.lang or UNDETERMINED
    by_user: dict[str, Counter] = defaultdict(Counter)
    for i in found:
        by_user[i.user_id[:8]][label(i)] += 1
    lines = [f"sources read: {len(found)}",
             "by language: " + ", ".join(f"{k} {v}" for k, v in Counter(map(label, found)).most_common()),
             "per user (first 8 characters of the id):"]
    for user, counts in sorted(by_user.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(f"  {user}: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))
    flagged = [i for i in found if i.lang and i.lang not in SUPPORTED]
    lines.append(f"not in a supported language: {len(flagged)} (user, source, input_type, lang, bytes)")
    lines += [f"  {i.user_id[:8]} {i.source_id[:8]} {i.input_type} {i.lang} {i.size}" for i in flagged]
    return "\n".join(lines)


def apply(client: Any, found: list[Identified]) -> int:
    todo = [i for i in found if i.lang and i.stored_lang is None]
    for i in todo:
        (client.table("sources").update({"lang": i.lang})
         .eq("source_id", i.source_id).eq("user_id", i.user_id).is_("lang", "null").execute())
    return len(todo)


def run(client: Any, *, write: bool) -> None:
    """Print the report; with write, set the missing languages. Shared by both entry points."""
    found = identify(fetch_sources(client, with_lang=write))
    print(report(found))
    if write:
        print(f"set lang on {apply(client, found)} sources (undetermined left NULL)")


def main(argv: list[str] | None = None) -> int:
    """Production entry point. Eval runs go through evals/backfill_source_lang.py, which
    loads the eval environment behind the guard before any backend module."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="set sources.lang (default: report only)")
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.confirm_production:
        parser.error("--apply on production needs --confirm-production")

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from db.supabase_client import supabase
    run(supabase, write=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
