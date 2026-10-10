"""Builders for review records and answers, shared by test_review.py and test_review_rules.py."""

import json
import re


def record(sentence: int, **changes) -> dict:
    """One compact sentence record that gives no issue (the author's opinion):
    only the four fields that are always given, plus the given changes."""
    return {"sentence": sentence, "content": "opinion", "stated_as": "authors_view",
            "presented_as": "authors_view", **changes}


def review_reply(numbers, changes: dict | None = None, rhythm=()) -> str:
    """A review answer with one benign record for each sentence number, with
    `changes[n]` applied to sentence n. `numbers` may be a count (1..count)."""
    changes = changes or {}
    numbers = range(1, numbers + 1) if isinstance(numbers, int) else numbers
    return json.dumps({"sentences": [record(n, **changes.get(n, {})) for n in numbers], "ai_rhythm": list(rhythm)})


def assigned(kwargs: dict) -> range:
    """The sentence numbers a review request assigns to its call."""
    first, last = re.search(r"Your assignment: sentences (\d+) to (\d+)\.", kwargs["messages"][-1]["content"]).groups()
    return range(int(first), int(last) + 1)


def answer_groups(claude, changes: dict | None = None, rhythm: dict | None = None, replace: dict | None = None) -> None:
    """Make the fake model answer every group call with records for exactly its
    assigned sentences. replace[first sentence of a group] overrides that group's
    whole reply (a string, a Message, or an exception to raise)."""
    def reply(kwargs):
        group = assigned(kwargs)
        override = (replace or {}).get(group[0])
        if isinstance(override, BaseException):
            raise override
        if override is not None:
            return override
        notes = [note for n, note in (rhythm or {}).items() if n in group]
        return review_reply(group, changes, notes)
    claude.respond_with(reply)
