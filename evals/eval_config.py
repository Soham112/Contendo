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
# The variants of the full ablation, in the order they are run and reported.
# B (Sonnet draft with review) is left out (Soham, 2026-10-10): in the smoke it
# was the most expensive Sonnet option and had the lowest judge score, and what
# the review is worth is still tested by B-Opus against C-Opus.
ABLATION_VARIANTS = ("A", "C", "B-Opus", "C-Opus")
# The decision rules, fixed before the full run (Soham, 2026-10-10). The one
# copy: ablation.md prints these (ablation.decision_rules_lines), and
# docs/plans/single-writer.md quotes them.
# "the 10 goldens" are the blind read's (BLIND_GOLDENS, below).
DECISION_RULES_DATE = "2026-10-10"
DECISION_RULES = (
    "C-Opus becomes the default if its unsupported_specifics pass count is at most 1 below B-Opus AND, in the "
    "blind read, B-Opus is ranked above C-Opus in 6 or fewer of the 10 goldens.",
    "B-Opus becomes the default if, in the blind read, it is ranked above C-Opus in 7 or more of the 10 goldens.",
    "A is retired if C or C-Opus is ranked above A in at least 5 of the 10 goldens.",
)
DECISION_TIEBREAK = (
    "Tiebreak if neither rule 1 nor rule 2 holds: hand-check C-Opus's judge failures beyond B-Opus's. Failures "
    "caused by the known authorship-framing problem (the author's own first-person notes framed as external, I1) "
    "are excluded from both variants' pass counts equally. Re-apply rule 1. If it still fails, B-Opus becomes the "
    'default ("never invents" outranks cost).'
)
DECISION_NOTE = ('"Clearly" better means ranked above in 7 of the 10 goldens, head to head. This is a practical bar, '
                 "not a statistical test.")
# Two edge cases, pinned the same day, before the run.
DECISION_FEWER_RANKED = (
    "The blind read uses only goldens for which every variant produced a post, so it has 10 complete goldens. "
    "If fewer than 10 are ranked, the thresholds apply as proportions of those ranked: \"clearly\" (rule 2) is at "
    "least 70%, rule 1's limit is at most 60%, rule 3 is at least 50%."
)
DECISION_AUDIT_BELOW = (
    "If the judge audit is below 8 of 10, rule 1's judge criterion is dropped: rules 1 and 2 are decided by the "
    "blind read alone, and the tiebreak does not apply."
)
# The same thresholds as shares of the goldens ranked (7, 6 and 5 of 10).
RULE_2_CLEARLY_SHARE = 0.7      # B-Opus above C-Opus in at least this share: rule 2
RULE_1_LIMIT_SHARE = 0.6        # B-Opus above C-Opus in at most this share: rule 1's blind-read condition
RULE_3_SHARE = 0.5              # C or C-Opus above A in at least this share: rule 3
# The head-to-head pairs the rules read from the blind read (first ranked above
# second), each with the conditions checked on the first one's share:
# (what it decides, "at_least" | "at_most", share).
BLIND_HEAD_TO_HEAD = (
    ("B-Opus", "C-Opus", (("rule 2 (B-Opus clearly above)", "at_least", RULE_2_CLEARLY_SHARE),
                          ("rule 1's blind-read condition", "at_most", RULE_1_LIMIT_SHARE))),
    ("C", "A", (("rule 3", "at_least", RULE_3_SHARE),)),
    ("C-Opus", "A", (("rule 3", "at_least", RULE_3_SHARE),)),
)
# Hard cap on what one ablation may spend, in USD at list prices, summed from
# measured usage across every script run with --ablation (spend.py). Set by
# Soham for the full run (2026-10-10); --spend-cap overrides it for one command.
EVAL_SPEND_CAP_USD = 14.0
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
# Blind read: goldens read, and the labels the posts of one golden get (one per
# variant, the first n of these; an ablation can have at most this many variants).
BLIND_GOLDENS = 10
BLIND_LABELS = ("V", "W", "X", "Y", "Z")
BLIND_SEED = 20261010
