"""Eval settings. No backend imports; models are named by their llm.client constant."""

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

# USD per million tokens (input, output), keyed by llm.client constant name.
# Anthropic list prices for claude-sonnet-4-6 and claude-haiku-4-5.
PRICES_PER_MTOK = {
    "SONNET": (3.00, 15.00),
    "HAIKU": (1.00, 5.00),
}


def call_cost(model_constant: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES_PER_MTOK[model_constant]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
