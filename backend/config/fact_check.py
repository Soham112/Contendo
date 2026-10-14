"""Legacy A checker settings. All live generation now ends with mandatory
synchronous grounding (pipeline.grounding); no log-only job is scheduled.
"""

# The retained A node: False = retired log-only record, discarded at the
# generation boundary. True = enforce before the final grounding gate (rewrite,
# re-check, remove). No-specifics mode is always enforced.
FACT_CHECK_ENFORCE_NORMAL_MODE = False
