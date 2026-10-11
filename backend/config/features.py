"""Feature flags and the pipeline variant."""

import os

# No-specifics ("opinion post without specifics") mode. Disabled until
# citation-based drafting lands in the pipeline redesign: the after-the-fact
# fixes (rewrite, re-check, repair) created dangling references, over-flagged
# generalisations and missed some first-person claims. While False, /generate
# rejects no_specifics=true with a 400 and run_pipeline refuses it too; the
# code paths and their tests stay (tests force the flag on).
NO_SPECIFICS_MODE_ENABLED = False


# ── Pipeline variant (ablation on feat/single-writer) ─────────────────────────
#
# Which post-draft pipeline run_pipeline uses:
#   A  the former pipeline: draft → critic → humanizer → audit → enforcer
#   B  single writer:    draft → checks → at most one redraft → compress
#   C  draft only:       draft → compress
#   B-Opus, C-Opus  B's and C's pipelines with another draft model
#           (llm.models.VARIANT_ROLE_MODELS)
# The default is C-Opus (decided 2026-10-10 from the pre-registered ablation
# "full": in the blind read C-Opus was ranked above B-Opus in 10 of 10 goldens
# and above A in 10 of 10). Under C and C-Opus every quality setting runs the
# same pipeline: there is no review, scorer or rewrite loop to switch.
# The PIPELINE_VARIANT environment variable overrides the default. Unset or
# empty means the default. PIPELINE_VARIANT=A is the rollback switch: it stays
# valid until pipeline A's code is removed (chore/remove-pipeline-a). Evals
# pass a variant to run_pipeline directly; it is never a /generate request field.
PIPELINE_VARIANTS = ("A", "B", "C", "B-Opus", "C-Opus")
# The graph each variant runs (pipeline.graph). A variant that differs from
# another only in its models shares that one's graph.
VARIANT_GRAPH = {"A": "A", "B": "B", "C": "C", "B-Opus": "B", "C-Opus": "C"}
DEFAULT_PIPELINE_VARIANT = "C-Opus"
PIPELINE_VARIANT_ENV = "PIPELINE_VARIANT"


class PipelineConfigError(RuntimeError):
    """PIPELINE_VARIANT (or a variant passed to run_pipeline) names no pipeline."""


def validate_pipeline_variant(variant: str) -> str:
    """variant if it is one of PIPELINE_VARIANTS, exactly as written there.
    Anything else raises: a typo must never quietly run a different pipeline."""
    if variant not in PIPELINE_VARIANTS:
        raise PipelineConfigError(
            f"Unknown pipeline variant {variant!r}: use one of {', '.join(PIPELINE_VARIANTS)}."
        )
    return variant


def pipeline_variant() -> str:
    """The configured variant. Read on every call, like config.security.current(),
    so there is no cached copy that can disagree with the environment. main.py
    calls this at startup, so the server refuses to start on an unknown value."""
    configured = os.environ.get(PIPELINE_VARIANT_ENV, "").strip()
    return validate_pipeline_variant(configured) if configured else DEFAULT_PIPELINE_VARIANT
