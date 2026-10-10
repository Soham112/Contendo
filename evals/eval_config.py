"""Eval settings. No backend imports; models are named by their llm.client constant.
Prices are not here: every cost comes from backend/llm/pricing.py."""

from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVALS_DIR / "results"

# Judge model: the name of a constant in backend/llm/client.py ("HAIKU" or "SONNET").
JUDGE_MODEL = "HAIKU"
# Each judge model writes its own scores file in results/<run_id>/.
SCORES_FILES = {"HAIKU": "scores.jsonl", "SONNET": "scores-sonnet.jsonl"}
JUDGE_MAX_TOKENS = 4000
JUDGE_EVENT_TYPE = "eval_judge"

# Pass thresholds (scores are 0-1). Starting points; tune after a few full runs.
THRESHOLDS = {
    "answer_relevancy": 0.7,
    "contextual_relevancy": 0.5,
    "faithfulness": 0.8,
    "unsupported_specifics": 0.7,
    "source_recall": 0.5,
}
METRIC_ORDER = tuple(THRESHOLDS)

# ── Ablation (docs/plans/single-writer.md, section 7) ─────────────────────────
ABLATIONS_DIR = RESULTS_DIR / "ablations"
INSTRUMENT_FILE = "instrument.jsonl"
# The two judged decision metrics and the judge each is read from. The judge
# model and its settings are the same for every variant.
ABLATION_JUDGES = {"unsupported_specifics": "SONNET", "answer_relevancy": JUDGE_MODEL}

# Judge audit: how many unsupported_specifics findings Soham marks, how many of
# them are the lowest scores (the rest are a seeded random sample), and how many
# must be marked correct for the metric to count as reliable (plan, section 7).
AUDIT_FINDINGS = 10
AUDIT_LOWEST = 5
AUDIT_MIN_CORRECT = 8
# Blind read: goldens read, and the labels the posts of one golden get.
BLIND_GOLDENS = 10
BLIND_LABELS = ("W", "X", "Y", "Z")
BLIND_SEED = 20261010
