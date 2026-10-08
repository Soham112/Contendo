"""Feature flags."""

# No-specifics ("opinion post without specifics") mode. Disabled until
# citation-based drafting lands in the pipeline redesign: the after-the-fact
# fixes (rewrite, re-check, repair) created dangling references, over-flagged
# generalisations and missed some first-person claims. While False, /generate
# rejects no_specifics=true with a 400 and run_pipeline refuses it too; the
# code paths and their tests stay (tests force the flag on).
NO_SPECIFICS_MODE_ENABLED = False
