"""Pure report building and results-file helpers. No env, no backend, no network."""

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

import eval_config as config


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


_REASON_CHARS = 400


def _latest(scores: Iterable[dict[str, Any]], judge_model: str) -> dict[tuple, dict[str, Any]]:
    """The last line per (golden, metric) for this judge model; later lines win."""
    latest: dict[tuple, dict[str, Any]] = {}
    for row in scores:
        if row.get("judge_model") == judge_model:
            latest[(row["golden_id"], row["metric"])] = row
    return latest


def _fmt(value: float | None, pct: bool = False) -> str:
    if value is None:
        return "–"
    return f"{value:.0%}" if pct else f"{value:.2f}"


def _stats(rows: list[dict[str, Any]]) -> tuple[int, float | None, float | None, int, int]:
    scored = [r for r in rows if r["status"] == "ok" and r.get("score") is not None]
    n = len(scored)
    avg = mean(r["score"] for r in scored) if scored else None
    passed = sum(1 for r in scored if r.get("success")) / n if n else None
    skipped = sum(1 for r in rows if r["status"] == "skipped")
    errors = sum(1 for r in rows if r["status"] == "error")
    return n, avg, passed, skipped, errors


def _breakdown(title: str, key: str, rows: list[dict[str, Any]], metrics: list[str]) -> list[str]:
    groups = sorted({r[key] for r in rows})
    lines = [f"## By {title}", "", f"| {title} | " + " | ".join(metrics) + " |",
             "|---|" + "---|" * len(metrics)]
    for group in groups:
        cells = []
        for m in metrics:
            n, avg, passed, _, _ = _stats([r for r in rows if r[key] == group and r["metric"] == m])
            cells.append(f"{_fmt(avg)} ({_fmt(passed, pct=True)} pass, n={n})" if n else "–")
        lines.append(f"| {group} | " + " | ".join(cells) + " |")
    return lines + [""]


def _fact_check_section(runs: list[dict[str, Any]]) -> list[str]:
    """Background (log-only) fact-check flags per drafted golden, from runs.jsonl."""
    checked = [r for r in runs if r.get("status") == "ok" and r.get("fact_check")]
    if not checked:
        return []
    flags = sum(len(r["fact_check"].get("flagged") or []) for r in checked)
    with_flags = sum(1 for r in checked if r["fact_check"].get("flagged"))
    errors = sum(1 for r in checked if r["fact_check"].get("outcome") == "error")
    lines = [
        "## Background fact-check flags (log-only)",
        "",
        f"{flags} flag(s) on {with_flags} of {len(checked)} drafted posts; {errors} check(s) errored. "
        "Log-only: nothing was changed in the posts. The find-prompt is known to over-flag paraphrases, "
        "so read these as leads, not verdicts.",
        "",
        "| golden | outcome | flags | types |",
        "|---|---|---|---|",
    ]
    for r in checked:
        flagged = r["fact_check"].get("flagged") or []
        types = ", ".join(sorted({f.get("type") or "?" for f in flagged})) or "–"
        lines.append(f"| {r['golden_id']} | {r['fact_check'].get('outcome')} | {len(flagged)} | {types} |")
    lines.append("")
    for r in checked:
        for f in r["fact_check"].get("flagged") or []:
            sentence = (f.get("sentence") or "").replace("\n", " ")
            lines.append(f"- **{r['golden_id']}** [{f.get('type')}] {sentence[:160]} (why: {f.get('why')})")
    return lines + [""]


def build_report(meta: dict[str, Any], runs: list[dict[str, Any]], scores: list[dict[str, Any]],
                 goldens: dict[str, dict[str, Any]], judge_model: str = config.JUDGE_MODEL,
                 metric_judges: dict[str, str] | None = None) -> str:
    """metric_judges: metric -> judge model for metrics judged by another model than
    judge_model (scores must then hold both models' rows)."""
    metric_judges = metric_judges or {}
    latest = {k: v for k, v in _latest(scores, judge_model).items() if k[1] not in metric_judges}
    for metric, model in metric_judges.items():
        latest.update({k: v for k, v in _latest(scores, model).items() if k[1] == metric})
    rows = list(latest.values())
    metrics = [m for m in config.METRIC_ORDER if any(r["metric"] == m for r in rows)]
    status_counts = defaultdict(int)
    for r in runs:
        status_counts[r.get("status", "unknown")] += 1

    git = meta.get("git", {})
    lines = [
        f"# Eval report: {meta['run_id']}",
        "",
        f"- Quality: **{meta['quality']}** · project `{meta['project_ref']}` · "
        f"commit `{git.get('commit', '?')}`{' (uncommitted changes)' if git.get('dirty') else ''}",
        f"- Judge: **{judge_model}** via `llm.client.complete()`"
        + "".join(f"; **{model}** for `{metric}`" for metric, model in metric_judges.items()),
        f"- Goldens: {len(runs)} run · {status_counts['ok']} ok · {status_counts['gated']} gated (low coverage, "
        f"not drafted or judged) · {status_counts['no_trace']} skipped (no trace) · {status_counts['error']} errored",
        "",
        "## Metrics",
        "",
        "| metric | n | mean | pass rate | threshold | skipped | errors |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in metrics:
        n, avg, passed, skipped, errors = _stats([r for r in rows if r["metric"] == m])
        lines.append(f"| {m} | {n} | {_fmt(avg)} | {_fmt(passed, pct=True)} | {config.THRESHOLDS[m]} | {skipped} | {errors} |")
    lines.append("")

    lines += _breakdown("difficulty", "difficulty", rows, metrics)
    lines += _breakdown("persona", "persona", rows, metrics)

    # Worst cases: lowest mean score across scored metrics.
    by_golden: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_golden[r["golden_id"]].append(r)
    ranked = []
    for gid, grows in by_golden.items():
        scored = [r["score"] for r in grows if r["status"] == "ok" and r.get("score") is not None]
        if scored:
            ranked.append((mean(scored), gid))
    ranked.sort()
    lines += ["## Worst cases", ""]
    for avg, gid in ranked[:5]:
        g = goldens.get(gid, {})
        lines.append(f"### {gid} · mean {avg:.2f} · {g.get('difficulty', '?')} · {g.get('persona', '?')}")
        lines.append(f"Topic: {g.get('topic', '?')}")
        lines.append("")
        for r in sorted(by_golden[gid], key=lambda r: config.METRIC_ORDER.index(r["metric"])):
            flag = "FAIL" if r.get("success") is False else ("skip" if r["status"] == "skipped" else
                                                              "error" if r["status"] == "error" else "pass")
            reason = (r.get("reason") or "").replace("\n", " ")
            if len(reason) > _REASON_CHARS:
                reason = reason[:_REASON_CHARS] + "…"
            lines.append(f"- **{r['metric']}** {_fmt(r.get('score'))} ({flag}): {reason}")
        lines.append("")

    lines += _fact_check_section(runs)

    # Cost.
    pipeline = [r["pipeline"] for r in runs if r.get("status") == "ok" and r.get("pipeline")]
    pipe_cost = sum(p["cost_usd"] for p in pipeline)
    pipe_calls = sum(p["calls"] for p in pipeline)
    judge_rows = [r for r in rows if r.get("judge_calls")]
    judge_cost_usd = sum(r["cost_usd"] for r in judge_rows)
    judge_calls = sum(r["judge_calls"] for r in judge_rows)
    n_ok = max(len(pipeline), 1)
    schema = defaultdict(int)
    for r in judge_rows:
        for k, v in (r.get("schema_paths") or {}).items():
            schema[k] += v
    lines += [
        "## Cost",
        "",
        "| | Claude calls | USD | per golden |",
        "|---|---|---|---|",
        f"| pipeline | {pipe_calls} | ${pipe_cost:.4f} | ${pipe_cost / n_ok:.4f} |",
        f"| judge | {judge_calls} | ${judge_cost_usd:.4f} | ${judge_cost_usd / n_ok:.4f} |",
        f"| **total** | {pipe_calls + judge_calls} | **${pipe_cost + judge_cost_usd:.4f}** | ${(pipe_cost + judge_cost_usd) / n_ok:.4f} |",
        "",
        "Pipeline cost is from each trace's `llm_calls`; judge cost from the judge's own `complete()` calls. "
        "Prices: `backend/llm/pricing.py`, by exact model id.",
        "",
        f"Judge structured output: {schema['tool']} via tool call, {schema['text_fallback']} needed the text fallback.",
        "",
    ]
    return "\n".join(lines)


def build_judge_comparison(rows_a: list[dict[str, Any]], rows_b: list[dict[str, Any]],
                           model_a: str, model_b: str, run_id: str) -> str:
    """Side by side per metric, over the (golden, metric) pairs both judges scored."""
    a = _latest(rows_a, model_a)
    b = _latest(rows_b, model_b)

    def scored(row: dict[str, Any] | None) -> bool:
        return row is not None and row["status"] == "ok" and row.get("score") is not None

    shared = sorted(k for k in a.keys() & b.keys() if scored(a[k]) and scored(b[k]))
    goldens = sorted({g for g, _ in shared})
    metrics = [m for m in config.METRIC_ORDER if any(k[1] == m for k in shared)]

    lines = [
        f"# Judge comparison: {model_a} vs {model_b} · {run_id}",
        "",
        f"Goldens judged by both: {', '.join(goldens) or 'none'}",
        "",
        f"| metric | n | mean {model_a} | mean {model_b} | pass {model_a} | pass {model_b} | verdicts differ |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in metrics:
        keys = [k for k in shared if k[1] == m]
        sa = [a[k]["score"] for k in keys]
        sb = [b[k]["score"] for k in keys]
        pa = sum(1 for k in keys if a[k].get("success")) / len(keys)
        pb = sum(1 for k in keys if b[k].get("success")) / len(keys)
        differ = [k[0] for k in keys if bool(a[k].get("success")) != bool(b[k].get("success"))]
        lines.append(f"| {m} | {len(keys)} | {mean(sa):.2f} | {mean(sb):.2f} | {pa:.0%} | {pb:.0%} | "
                     f"{', '.join(differ) or '–'} |")

    lines += ["", "## Per golden", "", "| golden | " + " | ".join(metrics) + " |", "|---|" + "---|" * len(metrics)]
    for g in goldens:
        cells = []
        for m in metrics:
            if (g, m) in shared:
                sa, sb = a[(g, m)]["score"], b[(g, m)]["score"]
                mark = " ⚠" if bool(a[(g, m)].get("success")) != bool(b[(g, m)].get("success")) else ""
                cells.append(f"{sa:.2f} / {sb:.2f}{mark}")
            else:
                cells.append("–")
        lines.append(f"| {g} | " + " | ".join(cells) + " |")
    lines += ["", f"Cells are {model_a} / {model_b}; ⚠ marks a pass/fail disagreement.", ""]

    cost_a = sum(r.get("cost_usd", 0) for k, r in a.items() if k[0] in goldens)
    cost_b = sum(r.get("cost_usd", 0) for k, r in b.items() if k[0] in goldens)
    lines += [f"Judge cost on these goldens: {model_a} ${cost_a:.4f} · {model_b} ${cost_b:.4f}", ""]
    return "\n".join(lines)
