"""Interleaved runs and the per-arm and per-golden tables of ablation.md.

Pure (run.py and ablation.build_ablation use it; tests import it without the
eval environment): the run order of an interleaved ablation, the fingerprints
of what each run drafted from, and markdown lines read from the runs.jsonl
rows (their post_record under "record"). Kept apart from ablation.py, which
holds the decision tables, to keep both files small.
"""

import hashlib
import json
import random
from collections import Counter
from typing import Any

from reporting import percentile

_FELL_BACK = "not an allowed type for these sources"


def arm_orders(golden_ids: list[str], variants: list[str], seed: int) -> dict[str, list[str]]:
    """The order the arms run in for each golden: a shuffle seeded by the seed
    and the golden's id, so it is random across goldens and reproducible."""
    orders = {}
    for golden_id in golden_ids:
        order = list(variants)
        random.Random(f"{seed}:{golden_id}").shuffle(order)
        orders[golden_id] = order
    return orders


def interleaved_pairs(goldens: list[dict[str, Any]], orders: dict[str, list[str]]) -> list[tuple[dict[str, Any], str]]:
    """(golden, variant) in the order an interleaved ablation runs them: golden
    by golden, each golden's arms in its own order."""
    return [(g, variant) for g in goldens for variant in orders[g["id"]]]


def input_fingerprints(trace: dict[str, Any]) -> dict[str, str]:
    """Short hashes of what a run drafted from: the retrieved chunks (ids and
    text, in order), the sources block the drafter was shown, the profile, and
    the plan (length target, perspective, retrieval confidence, gate decision).
    Runs of the same golden in one ablation must match on every one."""
    def digest(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:12]

    outputs = trace.get("node_outputs") or {}
    return {
        "retrieved": digest([(c.get("chunk_id"), c.get("text")) for c in trace.get("retrieved") or []]),
        "sources_block": digest(outputs.get("draft_frame_block") or ""),
        "profile": digest(trace.get("profile_snapshot") or {}),
        "plan": digest([outputs.get("length_target"), outputs.get("perspective"), trace.get("retrieval_confidence"),
                        (outputs.get("coverage_gate") or {}).get("decision")]),
    }




def _posts(variant: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in variant["runs"] if row.get("status") == "ok"]


def _pair(values: list[float], digits: int = 1, scale: float = 1.0) -> str:
    values = [v / scale for v in values if v is not None]
    if not values:
        return "–"
    return f"{percentile(values, 50):.{digits}f} / {percentile(values, 95):.{digits}f}"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header),
            *("| " + " | ".join(row) + " |" for row in rows), ""]


def _drafts(variant: dict[str, Any]) -> list[dict[str, Any]]:
    return [row["record"]["draft"] for row in _posts(variant) if row["record"].get("draft")]


def check_issues(posts: list[dict[str, Any]]) -> str:
    """Total issues the deterministic checks left on the final posts, by kind;
    "–" for runs recorded before post_record kept them."""
    recorded = [row["record"]["checks"] for row in posts if row["record"].get("checks") is not None]
    if not recorded:
        return "–"
    total = Counter()
    for counts in recorded:
        total.update(counts)
    listed = ", ".join(f"{key} {total[key]}" for key in sorted(total))
    return f"{sum(total.values())}" + (f" ({listed})" if total else "")


def speed_rows(variants: list[dict[str, Any]]) -> list[list[str]]:
    """Time to the draft's first text, and its thinking and output tokens, p50 / p95."""
    rows = []
    for v in variants:
        drafts = _drafts(v)
        rows.append([v["meta"]["variant"], str(len(drafts)),
                     _pair([d.get("first_text_ms") for d in drafts], 1, 1000.0),
                     _pair([d["thinking_tokens"] for d in drafts], 0),
                     _pair([d["output_tokens"] for d in drafts], 0)])
    return rows


def structure_rows(variants: list[dict[str, Any]]) -> list[list[str]]:
    """Who chose the structure, and how often the choice was not kept, by reason."""
    rows = []
    for v in variants:
        records = [row["record"] for row in _posts(v)]
        reasons = Counter(r.get("archetype_reason") for r in records if r.get("archetype_reason"))
        by = sorted({r.get("chosen_by") or "small_model" for r in records}) or ["–"]
        rows.append([v["meta"]["variant"], ", ".join(by), str(len(records)), str(reasons.get(_FELL_BACK, 0)),
                     ", ".join(f"{reason} {n}" for reason, n in sorted(reasons.items()) if reason != _FELL_BACK) or "–"])
    return rows


def _structure_cell(row: dict[str, Any] | None) -> str:
    if row is None or row.get("status") != "ok":
        return "–" if row is None else row.get("status", "–")
    record = row["record"]
    chosen, final = record.get("archetype_chosen"), record.get("archetype")
    return f"{chosen or '(none)'} → {final}" if chosen != final else str(final)


def _inputs_cell(rows: list[dict[str, Any]]) -> str:
    """"same" when every arm's run of the golden drafted from the same inputs, else the parts that differ."""
    prints = [row.get("inputs") for row in rows if row.get("inputs")]
    if len(prints) < 2:
        return "–"
    differ = sorted({part for p in prints[1:] for part in p if p.get(part) != prints[0].get(part)})
    return "same" if not differ else "DIFFERS: " + ", ".join(differ)


def golden_rows(variants: list[dict[str, Any]]) -> tuple[list[list[str]], list[list[str]]]:
    """(wall time per golden and arm, with the arm's position in that golden's
    run order; the structure per golden and arm, chosen → kept)."""
    names = [v["meta"]["variant"] for v in variants]
    by_golden: dict[str, dict[str, dict[str, Any]]] = {}
    for v in variants:
        for row in v["runs"]:
            by_golden.setdefault(row["golden_id"], {})[v["meta"]["variant"]] = row
    times, structures = [], []
    for golden_id in sorted(by_golden):
        rows = by_golden[golden_id]
        cells = []
        for name in names:
            row = rows.get(name)
            position = f" (#{row['arm_position']})" if row and row.get("arm_position") else ""
            cells.append("–" if row is None else f"{row.get('seconds', '–')} s{position}")
        times.append([golden_id, *cells, _inputs_cell(list(rows.values()))])
        structures.append([golden_id, *(_structure_cell(rows.get(name)) for name in names)])
    return times, structures


def detail_lines(variants: list[dict[str, Any]]) -> list[str]:
    names = [v["meta"]["variant"] for v in variants]
    times, structures = golden_rows(variants)
    return [
        "## Draft speed and tokens", "",
        "Time to first text is from the draft request to the first text of the reply (the thinking before it "
        "included), measured on the streamed draft call. Output tokens include thinking.", "",
        *_table(["variant", "drafts", "first text p50 / p95, s", "thinking tokens p50 / p95",
                 "output tokens p50 / p95"], speed_rows(variants)),
        "## Structure choice", "",
        "C's structure is chosen by the small model, D's by the drafter. \"Fell back to General\" counts posts "
        "whose chosen type was not on the allowed list.", "",
        *_table(["variant", "chosen by", "posts", "fell back to General", "other downgrades"], structure_rows(variants)),
        "## Per golden", "",
        "Wall time per run, with the arm's position in that golden's run order (#1 ran first). \"inputs\" says "
        "whether every arm drafted from the same retrieved chunks, sources block, profile and plan.", "",
        *_table(["golden", *names, "inputs"], times),
        "Structure per golden: chosen → kept (one name when the choice was kept).", "",
        *_table(["golden", *names], structures),
    ]
