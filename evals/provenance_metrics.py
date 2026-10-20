"""Scores for the provenance classifier (step 3.3). Pure functions.

A record is one case's labels and the classifier's answer:
    {"id", "split", "truth": label, "truth_paragraphs": {id: label}, "sizes": {id: chars},
     "result": None (no valid answer) | {"authorship", "confident", "paragraphs": {id: label}}}

The worst error is outside material applied as the user's own without asking:
a post would then claim it in first person. It is counted per paragraph, so an
outside passage inside the user's own note counts too.
"""
from typing import Any, Iterable

LABELS = ("user_authored", "external")
OWN, EXTERNAL = LABELS

# Targets agreed 2026-10-19 (CODEBASE.md "Step 3 data layer").
TARGETS = {
    "external_applied_as_own": 0,       # count of outside paragraphs, confident results only
    "own_applied_as_external": 0.05,    # share of the user's own sources, confident results only
    "applied_automatically": 0.80,      # share of sources with a confident result
    "run_agreement": 0.95,              # share of sources answered the same in two runs
}


def source_label(paragraphs: dict[int, str], sizes: dict[int, int]) -> str:
    """The label covering most characters; a tie is external (as the classifier decides)."""
    own = sum(sizes[i] for i, label in paragraphs.items() if label == OWN)
    other = sum(sizes[i] for i, label in paragraphs.items() if label == EXTERNAL)
    return OWN if own > other else EXTERNAL


def paragraph_truth(authorship: str, other: Iterable[int], sizes: dict[int, int]) -> dict[int, str]:
    """Each paragraph's label from a fixture's header. Raises ValueError when a
    listed paragraph does not exist or the header's label does not cover most
    of the text (it would contradict how the source label is decided)."""
    other = set(other)
    missing = other - set(sizes)
    if missing:
        raise ValueError(f"authorship_other lists paragraphs that do not exist: {sorted(missing)}")
    flipped = EXTERNAL if authorship == OWN else OWN
    truth = {i: flipped if i in other else authorship for i in sizes}
    if source_label(truth, sizes) != authorship:
        raise ValueError(f"authorship {authorship} does not cover most of the text")
    return truth


def predicted_paragraphs(authorship: str, spans: list[dict[str, Any]],
                         paragraphs: list[tuple[int, int, int]]) -> dict[int, str]:
    """Each (id, start, end) paragraph's label: its span's, else the source's."""
    labels = {}
    for pid, start, end in paragraphs:
        inside = [s["authorship"] for s in spans if s["start"] <= start and end <= s["end"]]
        labels[pid] = inside[0] if inside else authorship
    return labels


def _keys_to_int(mapping: dict) -> dict[int, Any]:
    return {int(k): v for k, v in mapping.items()}


def score(records: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(records)
    confusion = {t: {p: 0 for p in (*LABELS, "failed")} for t in LABELS}
    confident = own_sources = own_as_external = 0
    external_as_own: list[str] = []
    other_total = other_right = 0
    for r in records:
        result = r["result"]
        confusion[r["truth"]][result["authorship"] if result else "failed"] += 1
        own_sources += r["truth"] == OWN
        if not result:
            continue
        truth_p, pred_p = _keys_to_int(r["truth_paragraphs"]), _keys_to_int(result["paragraphs"])
        minority = [i for i, label in truth_p.items() if label != r["truth"]]
        other_total += len(minority)
        other_right += sum(pred_p.get(i) == truth_p[i] for i in minority)
        if result["confident"]:
            confident += 1
            wrong = [i for i, label in truth_p.items() if label == EXTERNAL and pred_p.get(i) == OWN]
            external_as_own += [f"{r['id']}#P{i}" for i in wrong]
            own_as_external += r["truth"] == OWN and result["authorship"] == EXTERNAL

    def precision(label: str) -> float | None:
        predicted = sum(confusion[t][label] for t in LABELS)
        return confusion[label][label] / predicted if predicted else None

    def recall(label: str) -> float | None:
        actual = sum(confusion[label].values())
        return confusion[label][label] / actual if actual else None

    return {
        "sources": n,
        "failed": sum(confusion[t]["failed"] for t in LABELS),
        "confusion": confusion,
        "precision": {label: precision(label) for label in LABELS},
        "recall": {label: recall(label) for label in LABELS},
        "applied_automatically": confident / n if n else None,
        "external_applied_as_own": len(external_as_own),
        "external_applied_as_own_where": external_as_own,
        "own_applied_as_external": own_as_external / own_sources if own_sources else None,
        "mixed_paragraph_recall": other_right / other_total if other_total else None,
    }


def agreement(run_a: dict[str, dict | None], run_b: dict[str, dict | None]) -> float | None:
    """Share of case ids both runs answered, whose answers are the same
    (source label, confident, every paragraph's label). No answer counts as an answer."""
    ids = sorted(set(run_a) & set(run_b))
    if not ids:
        return None

    def key(result: dict | None):
        if result is None:
            return None
        return result["authorship"], result["confident"], sorted(_keys_to_int(result["paragraphs"]).items())
    return sum(key(run_a[i]) == key(run_b[i]) for i in ids) / len(ids)


def verdicts(scores: dict[str, Any], run_agreement: float | None = None) -> dict[str, bool | None]:
    """Each target met (True), missed (False) or not measured (None)."""
    own = scores["own_applied_as_external"]
    auto = scores["applied_automatically"]
    return {
        "external_applied_as_own": scores["external_applied_as_own"] <= TARGETS["external_applied_as_own"],
        "own_applied_as_external": None if own is None else own <= TARGETS["own_applied_as_external"],
        "applied_automatically": None if auto is None else auto >= TARGETS["applied_automatically"],
        "run_agreement": None if run_agreement is None else run_agreement >= TARGETS["run_agreement"],
    }
