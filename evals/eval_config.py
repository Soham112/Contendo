"""Eval settings. No backend imports; models are named by their llm.client constant.
Prices are not here: every cost comes from backend/llm/pricing.py."""

from dataclasses import dataclass
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

# ── Ablation (CODEBASE.md §5, "C-Opus chosen by the full ablation") ─────────
ABLATIONS_DIR = RESULTS_DIR / "ablations"
# The variants of the full ablation, in the order they are run and reported.
# B (Sonnet draft with review) is left out (Soham, 2026-10-10): in the smoke it
# was the most expensive Sonnet option and had the lowest judge score, and what
# the review is worth is still tested by B-Opus against C-Opus.
ABLATION_VARIANTS = ("A", "C", "B-Opus", "C-Opus")
# The decision rules, fixed before the full run (Soham, 2026-10-10). The one
# copy: ablation.md prints these (ablation.decision_rules_lines), and
# CODEBASE.md §5 summarises the result.
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
@dataclass(frozen=True)
class AblationPlan:
    """What one named ablation runs and how it is decided. ablation.md prints
    the rules; blind.py scores the head-to-head pairs."""
    variants: tuple[str, ...]
    rules_date: str
    rules: tuple[str, ...]
    notes: tuple[str, ...]           # printed after the rules, in order
    head_to_head: tuple
    goldens: tuple[str, ...] = ()    # () means every golden
    run_regression: bool = True      # the review regression set (not part of any decision)
    interleave: bool = False         # run golden by golden, arms in a seeded random order (run.run_interleaved)
    seed: int = 0                    # the interleaved run order's seed


FULL_PLAN = AblationPlan(
    variants=ABLATION_VARIANTS, rules_date=DECISION_RULES_DATE, rules=DECISION_RULES,
    notes=(DECISION_TIEBREAK, DECISION_NOTE, DECISION_FEWER_RANKED, DECISION_AUDIT_BELOW),
    head_to_head=BLIND_HEAD_TO_HEAD,
)

# Phase 1 latency experiment (docs/GENERATION_ARCHITECTURE.md, section 15;
# result in CODEBASE.md §5, "One Opus call at effort low is the default"). Arms: a = C-Opus
# (today), b = D-Opus (structure folded into the Opus call), c = D-Opus-low
# (b at effort low; Opus 5.5 rejects thinking disabled at every effort). The
# 10 goldens are the full ablation's blind read (results/ablations/full/key.json).
# Rules: the Phase 0 report's, with grounding measured as the full ablation
# did, since the model grounding check left the request path on 2026-10-15.
PHASE1_CLEARLY_SHARE = 0.7      # C-Opus above an arm in at least this share keeps C-Opus over it
PHASE1_PLAN = AblationPlan(
    variants=("C-Opus", "D-Opus", "D-Opus-low"),
    rules_date="2026-10-14",
    rules=(
        "An arm (D-Opus, D-Opus-low) is eligible if its unsupported_specifics pass count (Sonnet judge) is at most "
        "1 below C-Opus's AND its final posts have no more deterministic check issues in total than C-Opus's.",
        "An eligible arm beats C-Opus on speed only if its p50 wall time is at least 15% lower than C-Opus's AND "
        "its p95 wall time is not higher than C-Opus's. If more than one arm qualifies, the one with the lowest p50 "
        "is the candidate.",
        "The candidate becomes the default unless, in the blind read, C-Opus is ranked above it in 7 or more of the "
        "10 goldens; then C-Opus stays the default. If no arm qualifies, C-Opus stays the default.",
    ),
    notes=(
        "The arms run golden by golden, in a seeded random order per golden, so the API's speed at a given time "
        "falls on every arm alike. Every arm of a golden must draft from the same inputs (retrieved chunks, sources "
        "block, profile, plan); the report checks it per golden.",
        "One run per golden per arm: p95 over 10 posts is close to the slowest post, so p50 is shown next to it. "
        "\"7 of 10\" is a practical bar, not a statistical test.",
        "The blind read uses only goldens for which every arm produced a post. If fewer than 10 are ranked, the bar "
        "is at least 70% of those ranked.",
        "If the judge audit is run and comes back below 8 of 10, rule 1's judge criterion is dropped: eligibility "
        "rests on the deterministic checks alone.",
    ),
    head_to_head=(
        ("C-Opus", "D-Opus", (("rule 3: C-Opus kept over D-Opus", "at_least", PHASE1_CLEARLY_SHARE),)),
        ("C-Opus", "D-Opus-low", (("rule 3: C-Opus kept over D-Opus-low", "at_least", PHASE1_CLEARLY_SHARE),)),
        ("D-Opus", "D-Opus-low", ()),
    ),
    goldens=("ds-02", "ds-05", "ds-06", "ds-09", "founder-01", "founder-02", "founder-04", "founder-05",
             "founder-09", "pm-02"),
    run_regression=False,
    interleave=True,
    seed=20261014,
)
PHASE1_SPEED_MARGIN = 0.15      # rule 2: p50 at least this much lower than C-Opus's
ABLATION_PLANS = {"phase1": PHASE1_PLAN}


def plan_for(name: str) -> AblationPlan:
    """The plan of a named ablation; any other name (full, smoke, ...) is the full ablation's."""
    return ABLATION_PLANS.get(name, FULL_PLAN)


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
