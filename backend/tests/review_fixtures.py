"""Builders for review records, shared by test_review.py and test_review_rules.py."""

import json


def record(sentence: int, **changes) -> dict:
    """One sentence record that gives no issue (the author's opinion, nothing
    linked, on topic), with the given fields changed."""
    return {
        "sentence": sentence, "content": "opinion", "stated_as": "authors_view", "supported_by": [],
        "evidence": None, "detail_differs": False, "differing_detail": None, "presented_as": "authors_view",
        "links_cause_or_sequence": False, "link_sources": [], "link_stated_by": [], "off_topic": False,
        **changes,
    }


def review_reply(count: int, changes: dict | None = None, rhythm=()) -> str:
    """A full review answer for a post of `count` sentences: benign records,
    with `changes[n]` applied to sentence n (1-based)."""
    changes = changes or {}
    return json.dumps({"sentences": [record(n, **changes.get(n, {})) for n in range(1, count + 1)],
                       "ai_rhythm": list(rhythm)})
