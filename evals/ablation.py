"""The variant ablation: what is recorded per post, and the ablation report.

Pure: no env, no backend, no network. run.py passes in the backend's own
functions (the price table, the two word counts) and stores the result in
runs.jsonl; report.py --variants reads those files and writes ablation.md.
"""

import math
from collections import Counter
from statistics import mean
from typing import Any, Callable, Iterable

import eval_config as config
from reporting import _fmt, _latest, _stats

# An issue type that only exists where a post has citations. Pipeline A's posts
# have none, and B corrects citations in code, so it is kept out of the count
# that compares variants and shown on its own.
CITATION_ONLY_ISSUES = ("wrong_citation",)
ROUTES = ("none", "code-only", "targeted", "full")
OUTCOMES = ("clean", "fixed", "issues_remain", "not_reviewed")
NO_POST_STATUSES = ("draft_truncated", "draft_refused")


def percentile(values: Iterable[float], p: float) -> float | None:
    """Nearest-rank percentile (p in 0-100); None for no values."""
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def summarize_llm_calls(calls: list[dict[str, Any]], call_cost: Callable[[str, int, int], float]) -> dict[str, Any]:
    """Calls, tokens and cost of a trace's llm_calls, in total and per model.
    call_cost is backend llm.pricing.call_cost: the one price table."""
    by_model: dict[str, dict[str, Any]] = {}
    for call in calls:
        entry = by_model.setdefault(call["model"], {"calls": 0, "input_tokens": 0, "output_tokens": 0,
                                                    "thinking_tokens": 0, "cost_usd": 0.0})
        tokens_in, tokens_out = call.get("input_tokens", 0), call.get("output_tokens", 0)
        entry["calls"] += 1
        entry["input_tokens"] += tokens_in
        entry["output_tokens"] += tokens_out
        entry["thinking_tokens"] += call.get("thinking_tokens", 0)
        entry["cost_usd"] += call_cost(call["model"], tokens_in, tokens_out)
    total = {key: sum(entry[key] for entry in by_model.values())
             for key in ("calls", "input_tokens", "output_tokens", "thinking_tokens", "cost_usd")}
    for entry in (total, *by_model.values()):
        entry["cost_usd"] = round(entry["cost_usd"], 6)
    return {**total, "by_model": by_model}


def length_record(post: str, target: dict[str, Any] | None,
                  counters: dict[str, Callable[[str], int]]) -> dict[str, dict[str, Any]]:
    """The post measured against its target once per counter: {counter name:
    {words, status: ok | over_length | under_length | no_target}}."""
    record = {}
    for name, count in counters.items():
        words = count(post)
        if target is None:
            status = "no_target"
        elif words > target["max_words"]:
            status = "over_length"
        elif words < target["min_words"]:
            status = "under_length"
        else:
            status = "ok"
        record[name] = {"words": words, "status": status}
    return record


def _route(review: dict[str, Any] | None) -> str | None:
    """Which path variant B took: none (nothing acted), code-only, targeted or
    full. None when the run had no review."""
    if review is None:
        return None
    if "fixes" not in review:
        return "none"
    return "code-only" if review["fixes"]["route"] == "none" else review["fixes"]["route"]


def post_record(outputs: dict[str, Any], calls: list[dict[str, Any]],
                counters: dict[str, Callable[[str], int]]) -> dict[str, Any]:
    """What the ablation reads from one generation trace (node_outputs and llm_calls)."""
    review = outputs.get("review")
    trim = outputs.get("trim_result")
    record: dict[str, Any] = {
        "length": length_record(outputs.get("final_post") or "", outputs.get("length_target"), counters),
        "route": _route(review),
        "outcome": (review or {}).get("outcome"),
        "redraft_unusable": next((kind for kind in ("redraft_truncated", "redraft_refused") if kind in (review or {})), None),
        "trim": None if trim is None else {"outcome": trim["outcome"], "reason": trim["reason"]},
        "removed": dict(Counter(item["kind"] for item in (review or {}).get("removed", []))),
        "remaining": dict(Counter(issue["type"] for issue in (review or {}).get("remaining", [])
                                  if issue["origin"] == "review")),
        "unreviewed": len((review or {}).get("unreviewed", [])),
        "multi_sentence_spans": outputs.get("multi_sentence_spans"),
        "draft": None,
    }
    drafts = [entry for entry in outputs.get("draft_history", []) if entry["node"] == "draft"]
    generate = [call for call in calls if call["event_type"] == "generate"]
    if "source_index" in outputs and drafts and generate:      # a single-writer draft: one call, marked output
        call, words = generate[0], counters["count_words"](drafts[0]["text"])
        written = call["output_tokens"] - call.get("thinking_tokens", 0)
        record["draft"] = {"model": call["model"], "output_tokens": call["output_tokens"],
                           "thinking_tokens": call.get("thinking_tokens", 0), "marked_words": words,
                           "tokens_per_word": round(written / words, 3) if words else None,
                           "stop_reason": call.get("stop_reason")}
    return record


# ── The report ────────────────────────────────────────────────────────────────

def _posts(variant: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in variant["runs"] if row.get("status") == "ok"]


def _mean(values: list[float]) -> float | None:
    return mean(values) if values else None


def _num(value: float | None, digits: int = 0, prefix: str = "") -> str:
    return "–" if value is None else f"{prefix}{value:,.{digits}f}"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header),
            *("| " + " | ".join(row) + " |" for row in rows), ""]


def _judged(variant: dict[str, Any], metric: str) -> str:
    model = config.ABLATION_JUDGES[metric]
    rows = [row for (_, m), row in _latest(variant["scores"].get(model, []), model).items() if m == metric]
    n, avg, passed, _, errors = _stats(rows)
    if not n:
        return "not judged"
    return f"{_fmt(avg)} ({_fmt(passed, pct=True)} pass, n={n}" + (f", {errors} errored)" if errors else ")")


def _length_cell(posts: list[dict[str, Any]], counter: str) -> str:
    statuses = Counter(row["record"]["length"][counter]["status"] for row in posts)
    measured = len(posts) - statuses["no_target"]
    return f"{statuses['over_length']} over, {statuses['under_length']} under (of {measured})"


def _counts(counter: Counter, keys: Iterable[str] | None = None) -> str:
    keys = list(keys) if keys is not None else sorted(counter)
    return ", ".join(f"{key} {counter[key]}" for key in keys) or "–"


def audit_label(audit: dict[str, Any] | None) -> str:
    """How far the unsupported_specifics judge can be trusted, from the hand audit."""
    if audit is None:
        return "not audited yet"
    if audit["marked"] < audit["of"]:
        return f"audit incomplete ({audit['marked']} of {audit['of']} marked)"
    verdict = "reliable" if audit["correct"] >= config.AUDIT_MIN_CORRECT else "UNRELIABLE"
    return f"{verdict}: {audit['correct']} of {audit['of']} audited findings judged correct"


def _decision_rows(variants: list[dict[str, Any]], audit: dict[str, Any] | None) -> list[list[str]]:
    def per_post(key: str, digits: int = 0, prefix: str = "") -> list[str]:
        return [_num(_mean([row["pipeline"][key] for row in _posts(v)]), digits, prefix) for v in variants]

    seconds = [[row["seconds"] for row in _posts(v)] for v in variants]
    return [
        [f"unsupported_specifics, Sonnet judge ({audit_label(audit)})", *(_judged(v, "unsupported_specifics") for v in variants)],
        ["answer relevancy (topic adherence)", *(_judged(v, "answer_relevancy") for v in variants)],
        ["wall time p50 / p90, s", *(f"{_num(percentile(s, 50), 1)} / {_num(percentile(s, 90), 1)}" for s in seconds)],
        ["cost per post", *per_post("cost_usd", 4, "$")],
        ["Claude calls per post", *per_post("calls", 1)],
        ["input tokens per post", *per_post("input_tokens")],
        ["output tokens per post", *per_post("output_tokens")],
        ["length violations, count_words", *(_length_cell(_posts(v), "count_words") for v in variants)],
        ["length violations, prose_word_count", *(_length_cell(_posts(v), "prose_word_count") for v in variants)],
    ]


def _run_rows(variants: list[dict[str, Any]]) -> list[list[str]]:
    rows = []
    for v in variants:
        statuses = Counter(row.get("status", "unknown") for row in v["runs"])
        used = sorted({model for row in v["runs"] for model in (row.get("pipeline") or {}).get("by_model", {})})
        git = v["meta"].get("git", {})
        rows.append([v["meta"]["variant"], v["meta"]["run_id"], ", ".join(used) or "–",
                     f"{git.get('commit', '?')}{' (dirty)' if git.get('dirty') else ''}",
                     f"{statuses['ok']} ok, {statuses['gated']} gated, {statuses['draft_truncated']} truncated, "
                     f"{statuses['draft_refused']} refused, {statuses['error'] + statuses['no_trace']} failed"])
    return rows


def _path_rows(variants: list[dict[str, Any]]) -> list[list[str]]:
    rows = []
    for v in variants:
        reviewed = [row["record"] for row in _posts(v) if row["record"]["route"] is not None]
        if not reviewed:
            continue
        routes = Counter(record["route"] for record in reviewed)
        outcomes = Counter(record["outcome"] for record in reviewed)
        unusable = Counter(record["redraft_unusable"] for record in reviewed if record["redraft_unusable"])
        rows.append([v["meta"]["variant"], str(len(reviewed)),
                     ", ".join(f"{route} {routes[route] / len(reviewed):.0%} ({routes[route]})" for route in ROUTES),
                     _counts(outcomes, OUTCOMES), _counts(unusable)])
    return rows


def _content_rows(variants: list[dict[str, Any]]) -> list[list[str]]:
    rows = []
    for v in variants:
        records = [row["record"] for row in _posts(v)]
        trims = [record["trim"] for record in records if record["trim"]]
        failed = Counter(trim["reason"] for trim in trims if trim["outcome"] == "trim_failed")
        removed = sum((Counter(record["removed"]) for record in records), Counter())
        spans = [record["multi_sentence_spans"] for record in records if record["multi_sentence_spans"] is not None]
        rows.append([v["meta"]["variant"], f"{len(trims)} run, {sum(failed.values())} failed" + (f" ({_counts(failed)})" if failed else ""),
                     _counts(removed),
                     f"{sum(spans)} in {sum(1 for s in spans if s)} of {len(spans)} drafts" if spans else "no citations"])
    return rows


def _instrument_rows(variants: list[dict[str, Any]]) -> list[list[str]]:
    rows = []
    for v in variants:
        reviewed = [row for row in v["instrument"] if row["status"] == "ok"]
        if not v["instrument"]:
            rows.append([v["meta"]["variant"], "not run", "–", "–", "–", "–"])
            continue
        by_type = sum((Counter(row["acting"]) for row in reviewed), Counter())
        compared = Counter({kind: n for kind, n in by_type.items() if kind not in CITATION_ONLY_ISSUES})
        with_any = sum(1 for row in reviewed if any(kind not in CITATION_ONLY_ISSUES for kind in row["acting"]))
        rows.append([v["meta"]["variant"], reviewed[0]["source"] if reviewed else "–",
                     f"{len(reviewed)} ({len(v['instrument']) - len(reviewed)} failed, "
                     f"{sum(1 for row in reviewed if row['outcome'] == 'not_reviewed')} not reviewed)",
                     f"{sum(compared.values())} on {with_any} post(s)", _counts(compared),
                     _counts(Counter({kind: by_type[kind] for kind in CITATION_ONLY_ISSUES if by_type[kind]}))])
    return rows


def _fact_check_rows(variants: list[dict[str, Any]]) -> list[list[str]]:
    rows = []
    for v in variants:
        checked = [row["fact_check"] for row in _posts(v) if (row.get("fact_check") or {}).get("outcome")]
        flags = [flag for check in checked for flag in check.get("flagged") or []]
        rows.append([v["meta"]["variant"], str(len(checked)), str(len(flags)),
                     str(sum(1 for check in checked if check.get("flagged"))),
                     _counts(Counter(flag.get("type") or "?" for flag in flags))])
    return rows


def _budget_rows(variants: list[dict[str, Any]]) -> list[list[str]]:
    """Per variant and draft model: output tokens (thinking excluded) per word
    of the marked draft, and the thinking the draft call used. The figures
    utils.formatters.TOKENS_PER_WORD and llm.client.THINKING_ALLOWANCE_TOKENS
    are set from."""
    rows = []
    for v in variants:
        drafts = [row["record"]["draft"] for row in v["runs"] if (row.get("record") or {}).get("draft")]
        for model in sorted({draft["model"] for draft in drafts}):
            mine = [draft for draft in drafts if draft["model"] == model]
            ratios = [draft["tokens_per_word"] for draft in mine if draft["tokens_per_word"] is not None]
            thinking = [draft["thinking_tokens"] for draft in mine]
            rows.append([v["meta"]["variant"], model, str(len(mine)),
                         f"{_num(_mean(ratios), 2)} (max {_num(max(ratios, default=None), 2)})",
                         f"{_num(percentile(thinking, 50))} / {_num(max(thinking, default=None))}",
                         _counts(Counter(draft["stop_reason"] for draft in mine if draft["stop_reason"] != "end_turn"))])
    return rows


def _blind_rows(blind: dict[str, Any]) -> list[list[str]]:
    return [[variant, _num(stats["mean_rank"], 2), str(stats["first"]), str(stats["last"]), str(stats["ranked"])]
            for variant, stats in blind["variants"].items()]


def build_ablation(name: str, variants: list[dict[str, Any]], audit: dict[str, Any] | None = None,
                   blind: dict[str, Any] | None = None) -> str:
    """ablation.md. variants: one {meta, runs, scores: {judge model: rows},
    instrument: rows} per run, in the order given; a run's rows carry the
    post_record() made when it ran. audit and blind are blind.py's results."""
    names = [v["meta"]["variant"] for v in variants]
    lines = [f"# Ablation: {name}", "",
             "Judges are the same for every variant: `unsupported_specifics` from "
             f"{config.ABLATION_JUDGES['unsupported_specifics']}, answer relevancy from "
             f"{config.ABLATION_JUDGES['answer_relevancy']} (`eval_config.py`). Per-post figures are means over "
             "the posts that were returned (status ok). Costs: `backend/llm/pricing.py`.", ""]
    lines += ["## Runs", "", *_table(["variant", "run", "models called", "commit", "goldens"], _run_rows(variants))]
    lines += ["## Decision metrics", "", *_table(["", *names], _decision_rows(variants, audit))]
    lines += ["Length is measured both ways on every final post: `count_words` counts every token (headings and "
              "placeholder lines included; pipeline A's measure), `prose_word_count` counts prose only (B's and C's).", ""]
    paths = _path_rows(variants)
    if paths:
        lines += ["## Review paths (variants that review)", "",
                  *_table(["variant", "reviewed posts", "route", "outcome", "redraft not usable"], paths)]
    lines += ["## Trim, removed content, citation compliance", "",
              *_table(["variant", "trims", "removed content by kind", "multi_sentence_spans"], _content_rows(variants))]
    lines += ["## Instrument: acting issues on the final post", "",
              "Record-only, and **the same reviewer as B, so biased in B's favour**: B was fixed against this "
              "reviewer's findings, A and C were not. For B the figures are the pipeline's own last review; for the "
              f"others the review was run on the final post afterwards. {', '.join(CITATION_ONLY_ISSUES)} is shown "
              "apart: A's posts have no citations to be wrong.", "",
              *_table(["variant", "from", "posts", "acting issues", "by type", "citation only"], _instrument_rows(variants))]
    lines += ["## Fact-check flags (low precision, not decisive)", "",
              "The background fact check over-flags paraphrases. Leads, not verdicts.", "",
              *_table(["variant", "posts checked", "flags", "posts with a flag", "by type"], _fact_check_rows(variants))]
    budget = _budget_rows(variants)
    if budget:
        lines += ["## Draft budget", "",
                  "Output tokens per word of the marked draft, thinking excluded, and the thinking tokens of the draft "
                  "call (truncated and refused drafts included).", "",
                  *_table(["variant", "draft model", "drafts", "tokens per word, mean", "thinking tokens p50 / max",
                           "not end_turn"], budget)]
    lines += ["## Blind read", ""]
    if blind is None:
        lines += ["Not scored yet (`python blind.py make`, then `score`). Orphaned sentences and flatness are judged there.", ""]
    else:
        lines += [f"{blind['ranked']} of {blind['goldens']} goldens ranked. Rank 1 is best.", "",
                  *_table(["variant", "mean rank", "ranked first", "ranked last", "n"], _blind_rows(blind))]
    return "\n".join(lines)
