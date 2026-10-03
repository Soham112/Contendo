"""Fact check settings (agents/fact_check_agent.py)."""

# Normal-mode posts: False = log-only (the check runs in the background after
# /generate responds and writes its flags to the trace; the post is never
# changed). True = enforce in the pipeline like no-specifics mode (rewrite,
# re-check, remove). No-specifics mode is always enforced.
FACT_CHECK_ENFORCE_NORMAL_MODE = False
