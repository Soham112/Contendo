"""Classify the authorship of existing sources (provenance step 3.3).

Every ready source nobody has labelled (authorship_set_by NULL) and that this
classifier version has not read yet goes through
agents.provenance_agent.classify_provenance, as new ingests do; the result is
written by memory.authorship_store.write_classifier_result (label only when
confident, authorship_detail always, chunk labels rewritten).

Production, from backend/ (reads backend/.env):
    venv/bin/python -m scripts.backfill_authorship                     # estimate only: $0, no model calls
    venv/bin/python -m scripts.backfill_authorship --apply --confirm-production [--spend-cap 2.00]   # PAID
Eval, from the repo root, through the evals env guard:
    backend/venv/bin/python evals/backfill_authorship.py [--apply] [--spend-cap 2.00]

--apply asks before spending and stops before the next source once the
measured spend reaches the cap. Re-running is safe: sources already read by
this classifier version, labelled by the user or a rule, or being replaced are
skipped. The review list shows every source where the classifier's label
differs from what its memory_context implies (learning = someone else's,
work / personal_project / observation = the user's), for a person to check.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

PAGE = 1000  # PostgREST's maximum rows per request
DEFAULT_SPEND_CAP_USD = 2.00
SOURCE_COLUMNS = ("source_id,user_id,status,input_type,title,title_origin,author,extracted_text,"
                  "ingest_id,pending_replace,authorship,authorship_set_by,authorship_detail")
# What memory_context implies about authorship, for the review list only.
CONTEXT_IMPLIES = {"learning": "external", "work": "user_authored",
                   "personal_project": "user_authored", "observation": "user_authored"}


@dataclass
class Candidate:
    row: dict
    source_type: str
    memory_context: str | None


def _paged(client: Any, table: str, columns: str, build: Callable[[Any], Any] = lambda q: q) -> list[dict]:
    rows: list[dict] = []
    while True:
        query = build(client.table(table).select(columns)).order("id" if table == "embeddings" else "source_id")
        page = query.range(len(rows), len(rows) + PAGE - 1).execute().data or []
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def _chunk_facts(client: Any) -> dict[tuple[str, str], tuple[str, str | None]]:
    """(user_id, source_id) -> (source_type, memory_context) from each source's chunks."""
    facts: dict[tuple[str, str], tuple[str, str | None]] = {}
    for r in _paged(client, "embeddings", "id,user_id,source_id,source_type,memory_context",
                    lambda q: q.eq("node_type", "chunk")):
        facts.setdefault((r["user_id"], r["source_id"]), (r.get("source_type") or "", r.get("memory_context")))
    return facts


def _skip_reason(row: dict, version: str) -> str | None:
    if row.get("status") != "ready":
        return "not ready"
    if row.get("pending_replace"):
        return "being replaced"
    if row.get("authorship_set_by"):
        return f"set by {row['authorship_set_by']}"
    read_by = ((row.get("authorship_detail") or {}).get("classifier") or {}).get("version")
    if read_by == version:
        return "already read by this classifier version"
    if not (row.get("extracted_text") or "").strip():
        return "no text"
    return None


def select(client: Any) -> tuple[list[Candidate], Counter]:
    """The sources to classify, and how many were skipped for which reason."""
    from agents.provenance_agent import CLASSIFIER

    facts = _chunk_facts(client)
    todo: list[Candidate] = []
    skipped: Counter = Counter()
    for row in _paged(client, "sources", SOURCE_COLUMNS):
        reason = _skip_reason(row, CLASSIFIER[1])
        if reason:
            skipped[reason] += 1
            continue
        source_type, memory_context = facts.get((row["user_id"], row["source_id"]), ("", None))
        todo.append(Candidate(row, source_type, memory_context))
    return todo, skipped


def _facts(c: Candidate):
    from agents.provenance_prompt import SourceFacts
    r = c.row
    return SourceFacts(title=r.get("title") or "", title_origin=r.get("title_origin"),
                       input_type=r.get("input_type") or "", source_type=c.source_type,
                       provider_author=r.get("author"))


def estimate(todo: list[Candidate], author_for: Callable[[str], Any]) -> dict[str, Any]:
    """Expected and upper-bound USD of classifying `todo` (provenance_agent.call_costs); $0."""
    from agents.provenance_agent import call_costs, estimated_tokens, request_chars

    pairs = [estimated_tokens(chars) for c in todo
             for chars in request_chars(c.row["extracted_text"], facts=_facts(c), author=author_for(c.row["user_id"]))]
    calls, tokens, expected, upper = call_costs(pairs)
    return {"sources": len(todo), "calls": calls, "input_tokens": tokens,
            "expected_usd": expected, "upper_usd": upper}


def disagreement(c: Candidate, label: str) -> str | None:
    """A review line when the classifier's label differs from what memory_context implies."""
    implied = CONTEXT_IMPLIES.get(c.memory_context or "")
    if implied is None or implied == label:
        return None
    title = (c.row.get("title") or "")[:60]
    return (f"  {c.row['user_id'][:8]} {c.row['source_id']} {c.row.get('input_type')} "
            f"memory_context={c.memory_context} classifier={label} | {title}")


def apply(todo: list[Candidate], author_for: Callable[[str], Any], cap_usd: float) -> dict[str, Any]:
    """Classify and write each source until the measured spend reaches the cap."""
    from agents.provenance_agent import classify_provenance
    from llm.client import trace_calls
    from llm.pricing import call_cost
    from memory.authorship_store import write_classifier_result

    spent = 0.0
    counts: Counter = Counter()
    review: list[str] = []
    for n, c in enumerate(todo):
        if spent >= cap_usd:
            counts["left by the spend cap"] = len(todo) - n
            break
        user_id = c.row["user_id"]
        error = None
        with trace_calls() as calls:
            try:
                result = classify_provenance(c.row["extracted_text"], facts=_facts(c),
                                             author=author_for(user_id), user_id=user_id)
            except Exception as exc:   # an API error: stop, keeping what is written
                error = f"{c.row['source_id']}: {type(exc).__name__}: {exc}"
        spent += sum(call_cost(k["model"], k["input_tokens"], k["output_tokens"]) for k in calls)
        if error:
            counts[f"stopped by an error ({error}); re-run to continue"] = len(todo) - n
            break
        if result is None:
            counts["no valid answer (left unknown)"] += 1
            continue
        label = result.authorship if result.confident else None
        if not write_classifier_result(c.row, user_id, authorship=label, detail=result.detail()):
            counts["changed meanwhile (not written)"] += 1
            continue
        counts[f"{result.authorship} ({'applied' if result.confident else 'not confident: ask the user'})"] += 1
        line = disagreement(c, result.authorship)
        if line:
            review.append(line + ("" if result.confident else " [not confident]"))
    return {"spent_usd": spent, "counts": counts, "review": review}


def run(client: Any, *, write: bool, cap_usd: float, confirm: Callable[[str], bool]) -> int:
    """Print the estimate; with write (and confirmation), classify and report. Shared by both entry points."""
    from agents.provenance_agent import author_context

    contexts: dict[str, Any] = {}

    def author_for(user_id: str):
        if user_id not in contexts:
            contexts[user_id] = author_context(user_id)
        return contexts[user_id]

    todo, skipped = select(client)
    cost = estimate(todo, author_for)
    print(f"to classify: {cost['sources']} sources, {cost['calls']} calls, {cost['input_tokens']} input tokens "
          f"(estimated). Expected ${cost['expected_usd']:.4f}, upper bound ${cost['upper_usd']:.4f}.")
    print("skipped: " + (", ".join(f"{k} {v}" for k, v in skipped.most_common()) or "none"))
    if not write or not todo:
        return 0
    if not confirm(f"Spend up to ${cap_usd:.2f}? [y/N] "):
        print("Nothing spent.")
        return 1
    done = apply(todo, author_for, cap_usd)
    print(f"Measured spend: ${done['spent_usd']:.4f} (cap ${cap_usd:.2f})")
    for k, v in done["counts"].most_common():
        print(f"  {k}: {v}")
    print(f"review (classifier differs from memory_context): {len(done['review'])}")
    print("\n".join(done["review"]))
    return 0


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--apply", action="store_true", help="classify and write (PAID; default: estimate only)")
    parser.add_argument("--spend-cap", type=float, default=DEFAULT_SPEND_CAP_USD)
    parser.add_argument("--yes", action="store_true", help="skip the spend confirmation")


def confirmer(yes: bool) -> Callable[[str], bool]:
    return (lambda _: True) if yes else (lambda prompt: input(prompt).strip().lower() == "y")


def main(argv: list[str] | None = None) -> int:
    """Production entry point. Eval runs go through evals/backfill_authorship.py, which
    loads the eval environment behind the guard before any backend module."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_arguments(parser)
    parser.add_argument("--confirm-production", action="store_true")
    args = parser.parse_args(argv)
    if args.apply and not args.confirm_production:
        parser.error("--apply on production needs --confirm-production")

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    from db.supabase_client import supabase
    return run(supabase, write=args.apply, cap_usd=args.spend_cap, confirm=confirmer(args.yes))


if __name__ == "__main__":
    raise SystemExit(main())
