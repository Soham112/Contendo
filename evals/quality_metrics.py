"""The retrieval scorecard (docs/QUALITY.md B1) for one case, and its aggregates. Pure functions.

Inputs are label ids in rank order, one per source (its first chunk's rank):
`drafted` is what reaches the drafter (empty when the coverage gate stops the
run), `retrieved` is what retrieval returned before the gate. The cutoff is the
number of sources that reach the drafter, so @cutoff is what the drafter sees.

Required evidence is counted in units: each must_use_all source is one unit, and
a must_use_any group is one unit that any of its sources satisfies.

Two labels are not sources a case can be labelled with and are scored apart:
    CONSOLIDATION  a consolidation chunk (derived from several sources); excluded from precision
    UNLABELLED     a source the case doesn't label; for verified cases it counts against
                   precision, for metadata_only cases it is excluded (the labels are partial)

Not here yet: Evidence Recall@K (did the drafter's context contain the labelled
fact, not only the right source). It needs fact labels, which step 3 adds.
"""
from typing import Any

CONSOLIDATION = "consolidation"
UNLABELLED = "unlabelled"
PRECISION_PASS = 0.75  # docs/QUALITY.md criterion 2; to tune on the baseline distribution
DIAGNOSTIC_K = (1, 3, 5)


def _units(case: dict[str, Any]) -> list[set[str]]:
    units = [{s} for s in case["must_use_all"]]
    if case["must_use_any"]:
        units.append(set(case["must_use_any"]))
    return units


def _required(case: dict[str, Any]) -> set[str]:
    return set(case["must_use_all"]) | set(case["must_use_any"])


def recall_at(case: dict[str, Any], labels: list[str], k: int | None = None) -> float | None:
    """Share of required units present in the top k (None: the whole list)."""
    units = _units(case)
    if not units:
        return None
    top = set(labels if k is None else labels[:k])
    return round(sum(1 for unit in units if unit & top) / len(units), 3)


def recall(case: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """Required-source Recall@K: at the cutoff (pass: every unit), and @1/@3/@5 for diagnosis."""
    value = recall_at(case, labels)
    return {"at_cutoff": value, "cutoff": len(labels),
            "at": {k: recall_at(case, labels, k) for k in DIAGNOSTIC_K},
            "pass": None if value is None else value == 1.0}


def mrr(case: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """Reciprocal rank of the first required source (0 when none arrives). Pass:
    rank 1 for topics that name a project, company or role, top 3 otherwise."""
    required = _required(case)
    if not required:
        return {"value": None, "first_rank": None, "pass": None}
    rank = next((i for i, l in enumerate(labels, 1) if l in required), None)
    limit = 1 if case["phrasing"] == "names_project" else 3
    return {"value": round(1 / rank, 3) if rank else 0.0, "first_rank": rank,
            "pass": rank is not None and rank <= limit}


def _counted(case: dict[str, Any], labels: list[str]) -> list[str]:
    counted = [l for l in labels if l != CONSOLIDATION]
    if case["label_confidence"] == "metadata_only":
        counted = [l for l in counted if l != UNLABELLED]
    return counted


def precision(case: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """Precision@cutoff: share of drafter sources that are required or background."""
    good = _required(case) | set(case["background"])
    counted = _counted(case, labels)
    if not counted:
        return {"value": None, "pass": None}
    value = sum(1 for l in counted if l in good) / len(counted)
    return {"value": round(value, 3), "pass": value >= PRECISION_PASS}


def off_topic(case: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """Off-topic rate among drafter sources; pass when none arrives."""
    found = [l for l in labels if l in set(case["off_topic"])]
    counted = _counted(case, labels)
    return {"value": found, "rate": round(len(found) / len(counted), 3) if counted else 0.0, "pass": not found}


def own_share(case: dict[str, Any], labels: list[str], own_ids: frozenset[str] | None) -> dict[str, Any]:
    """For topics that name a project, company or role: at least one own source
    and own sources at least half of the drafter's sources."""
    if case["phrasing"] != "names_project" or own_ids is None:
        return {"value": None, "pass": None}
    counted = [l for l in labels if l != CONSOLIDATION]
    if not counted:
        return {"value": 0.0, "pass": False}
    own = sum(1 for l in counted if l in own_ids)
    value = own / len(counted)
    return {"value": round(value, 3), "pass": own > 0 and value >= 0.5}


def gate_accuracy(case: dict[str, Any], decision: str | None) -> bool | None:
    """Whether the coverage gate matches the labelled coverage (none -> stopped,
    full -> not stopped). Partial coverage has no expectation."""
    if case["coverage"] == "partial":
        return None
    stopped = decision == "low_coverage"
    return stopped if case["coverage"] == "none" else not stopped


def hybrid_reliability(bm25: dict[str, Any], retrieval_path: str | None, attempts: int) -> dict[str, Any]:
    """Both halves of hybrid search ran: the hybrid path (no silent fallback) and
    BM25 over the whole library. Retries are recorded, not hidden."""
    base = {**bm25, "retrieval_path": retrieval_path, "attempts": attempts}
    if retrieval_path != "hybrid":
        return {**base, "pass": False}
    if not bm25.get("library_chunks"):
        return {**base, "pass": None}  # empty library: nothing to search
    ran = bool(bm25.get("ran")) and not bm25.get("error")
    return {**base, "pass": ran and bm25.get("corpus_size") == bm25.get("library_chunks")}


def score_case(case: dict[str, Any], drafted: list[str], retrieved: list[str], own_ids: frozenset[str] | None,
               decision: str | None, bm25: dict[str, Any], retrieval_path: str | None = "hybrid",
               attempts: int = 1) -> dict[str, Any]:
    return {
        "recall": recall(case, drafted),
        "recall_before_gate": recall(case, retrieved),
        "mrr": mrr(case, drafted),
        "precision": precision(case, drafted),
        "off_topic": off_topic(case, drafted),
        "own_share": own_share(case, drafted, own_ids),
        "gate_accuracy": gate_accuracy(case, decision),
        "hybrid_reliability": hybrid_reliability(bm25, retrieval_path, attempts),
        "gate": decision,
    }


CRITERIA = ("recall", "mrr", "precision", "off_topic", "own_share", "gate_accuracy", "hybrid_reliability")


def _verdict(score: dict[str, Any], key: str) -> bool | None:
    value = score[key]
    return value if key == "gate_accuracy" else value["pass"]


def pass_rates(scores: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """criterion -> (passed, applicable) over cases where it applies."""
    out = {}
    for key in CRITERIA:
        verdicts = [v for v in (_verdict(s, key) for s in scores) if v is not None]
        out[key] = (sum(1 for v in verdicts if v), len(verdicts))
    return out


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 3) if present else None


def means(scores: list[dict[str, Any]]) -> dict[str, float | None]:
    """Mean Recall@1/3/5/cutoff, MRR, Precision@cutoff and off-topic rate over cases where each applies."""
    out = {f"recall@{k}": _mean([s["recall"]["at"][k] for s in scores]) for k in DIAGNOSTIC_K}
    out["recall@cutoff"] = _mean([s["recall"]["at_cutoff"] for s in scores])
    out["mrr"] = _mean([s["mrr"]["value"] for s in scores])
    out["precision@cutoff"] = _mean([s["precision"]["value"] for s in scores])
    out["off_topic_rate"] = _mean([s["off_topic"]["rate"] if s["recall"]["cutoff"] else None for s in scores])
    return out
