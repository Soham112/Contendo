"""Feature flags and the pipeline variant."""

import os


def business_block_enabled() -> bool:
    """Read dynamically so rollback also changes retrieval and its cache."""
    return os.environ.get("BUSINESS_BLOCK_ENABLED", "1").strip().lower() not in {"0", "false", "off"}

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
#   D-Opus  one call: C without the separate structure call. The drafter (Opus)
#           chooses the structure among the types the code allows and names it
#           in its output (pipeline/single_writer.wire_one_call)
#   D-Opus-low  D-Opus with the draft call at effort "low"
#           (llm.models.VARIANT_DRAFT_EFFORT)
# D-Opus and D-Opus-low are the Phase 1 latency experiment's arms
# (docs/GENERATION_ARCHITECTURE.md, section 15; evals ablation "phase1").
# The default is D-Opus-low (decided 2026-10-15 from the pre-registered evals
# ablation "phase1", 10 goldens, arms run interleaved with identical inputs;
# docs/GENERATION_ARCHITECTURE.md section 17):
#   rule 1 (eligible): D-Opus and D-Opus-low both, unsupported_specifics 10 of
#     10 passes like C-Opus, deterministic check issues 5 and 8 against 9.
#   rule 2 (speed: p50 at least 15% lower, p95 not higher than C-Opus's 14.9 /
#     46.9 s): D-Opus-low qualifies at 7.0 / 18.2 s; D-Opus does not (14.3 s p50).
#   rule 3 (blind read): C-Opus was ranked above D-Opus-low in 3 of 10 goldens,
#     below the 7 that would keep it. Mean rank D-Opus-low 1.70, D-Opus 2.10,
#     C-Opus 2.20; D-Opus-low first in 6 of 10.
# The previous default was C-Opus (2026-10-10, ablation "full"). Under C and D
# every quality setting runs the same pipeline: there is no review, scorer or
# rewrite loop to switch.
# The PIPELINE_VARIANT environment variable overrides the default. Unset or
# empty means the default. Rollback switches: PIPELINE_VARIANT=C-Opus (the
# previous default) and PIPELINE_VARIANT=A, which stays valid until pipeline
# A's code is removed (chore/remove-pipeline-a). Evals
# pass a variant to run_pipeline directly; it is never a /generate request field.
PIPELINE_VARIANTS = ("A", "B", "C", "B-Opus", "C-Opus", "D-Opus", "D-Opus-low")
# The graph each variant runs (pipeline.graph). A variant that differs from
# another only in its models shares that one's graph.
VARIANT_GRAPH = {"A": "A", "B": "B", "C": "C", "B-Opus": "B", "C-Opus": "C", "D-Opus": "D", "D-Opus-low": "D"}
DEFAULT_PIPELINE_VARIANT = "D-Opus-low"
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
