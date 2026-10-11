"""Two sources shared by the checks and review tests (test_checks.py, test_review.py)."""

# S1: the author's own note. S2: something the author read.
PRICING = {"memory_context": "work", "source_type": "note", "source_title": "Pricing test", "tags": "pricing",
           "text": ("Results: conversion improved from 13 to 16 percent; average revenue per account fell 4 percent; "
                    "shared logins rose. Early meetings were me presenting slides for an hour. "
                    "The rollout took three months.")}
SURVEY = {"memory_context": "learning", "source_type": "article", "source_title": "Review survey", "tags": "reviews",
          "text": "The survey found that 41 percent of teams skip reviews. Churn fell by a third at the firms that did not."}
