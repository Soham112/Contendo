"""Model ids, what each model's API accepts, and which model each role uses.

The only place model id strings live. llm/client.py sends the calls,
llm/pricing.py prices them, config/features.py names the pipeline variants.

Ids, prices and call shapes were checked against the Anthropic docs on
2026-10-10 (models overview, pricing, thinking, define-tools "Forcing tool
use", handling stop reasons): https://platform.claude.com/docs/en/about-claude/models/overview
"""

from dataclasses import dataclass
from typing import Any, Mapping

SONNET_4_6 = "claude-sonnet-4-6"
HAIKU_4_5 = "claude-haiku-4-5-20251001"
OPUS_5_5 = "claude-opus-5-5"
SONNET_5_5 = "claude-sonnet-5-5"
HAIKU_5_5 = "claude-haiku-5-5"

# Tokenizer generations. The one introduced with Claude Opus 4.7 produces about
# 30% more tokens for the same text, so anything budgeted in tokens per word
# (utils.formatters.TOKENS_PER_WORD) is kept per tokenizer.
TOKENIZER_CLAUDE_4 = "claude-4"
TOKENIZER_CLAUDE_4_7 = "claude-4.7"


@dataclass(frozen=True)
class ModelSpec:
    """What a call to this model has to allow for.

    thinks: thinking is on when the request does not configure it. The reply
      can then begin with thinking blocks (read the text blocks by type, never
      content[0]), and thinking counts against max_tokens.
    forced_tool_choice: whether tool_choice {"type": "tool"} is accepted. Where
      it is not (a 400), a structured call sends tool_choice "auto" and says in
      the prompt to call the tool (llm.client.complete_structured).
    default_effort: the API's own effort level when none is sent. Nothing here
      sends one; it is recorded so a run's settings can be read back.
    """
    tokenizer: str
    thinks: bool
    forced_tool_choice: bool
    default_effort: str | None

# Any model can end a reply with stop_reason "refusal" (HTTP 200, no error); the
# 5.5 models run more classifiers that do. Callers check stop_reason and turn a
# refusal into an explicit status, whatever the model.


MODELS: dict[str, ModelSpec] = {
    SONNET_4_6: ModelSpec(TOKENIZER_CLAUDE_4, thinks=False, forced_tool_choice=True, default_effort="high"),
    HAIKU_4_5: ModelSpec(TOKENIZER_CLAUDE_4, thinks=False, forced_tool_choice=True, default_effort=None),
    OPUS_5_5: ModelSpec(TOKENIZER_CLAUDE_4_7, thinks=True, forced_tool_choice=False, default_effort="medium"),
    SONNET_5_5: ModelSpec(TOKENIZER_CLAUDE_4_7, thinks=True, forced_tool_choice=False, default_effort="high"),
    # Accepts a forced tool call, and such a call skips thinking.
    HAIKU_5_5: ModelSpec(TOKENIZER_CLAUDE_4_7, thinks=True, forced_tool_choice=True, default_effort="medium"),
}


# ── Roles (single-writer pipeline, variants B and C) ──────────────────────────
#
# Pipeline A does not use roles: its agents keep llm.client.SONNET and HAIKU.
DRAFT_MODEL = SONNET_4_6     # the draft, the targeted fix and the full redraft
REVIEW_MODEL = SONNET_4_6    # the structured review
SMALL_MODEL = HAIKU_4_5      # the structure choice and the trim

ROLE_MODELS: dict[str, str] = {"draft": DRAFT_MODEL, "review": REVIEW_MODEL, "small": SMALL_MODEL}

# What a variant changes from ROLE_MODELS. Keys are names in
# config.features.PIPELINE_VARIANTS (tests/test_models.py checks that).
VARIANT_ROLE_MODELS: dict[str, dict[str, str]] = {
    "B-Opus": {"draft": OPUS_5_5},
}


class ModelConfigError(ValueError):
    """A role or a model id that this module does not know."""


def spec(model: str) -> ModelSpec:
    if model not in MODELS:
        raise ModelConfigError(f"Unknown model {model!r}: add it to llm.models.MODELS and llm.pricing.PRICES.")
    return MODELS[model]


def role_models(variant: str, overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """The model each role uses under this variant: ROLE_MODELS, then the
    variant's own changes, then `overrides` (evals only, e.g. the small-model
    check). An unknown role or model raises."""
    chosen = {**ROLE_MODELS, **VARIANT_ROLE_MODELS.get(variant, {}), **(overrides or {})}
    unknown = sorted(set(chosen) - set(ROLE_MODELS))
    if unknown:
        raise ModelConfigError(f"Unknown model role(s) {unknown}: use one of {sorted(ROLE_MODELS)}.")
    for model in chosen.values():
        spec(model)
    return chosen


def model_for(state: Mapping[str, Any], role: str) -> str:
    """The model this run uses for a role: what run_pipeline put in
    state["models"], or the configured ROLE_MODELS for a state built without
    run_pipeline (a node called on its own)."""
    return (state.get("models") or ROLE_MODELS)[role]
