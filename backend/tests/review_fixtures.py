"""Builders for review records and answers, shared by test_review.py,
test_review_rules.py and the variant B pipeline tests (test_pipeline_b.py)."""

import json
import re

from tests.conftest import ARCHETYPE_GENERAL
from tests.generation_fixtures import enveloped  # noqa: F401  (also imported from here)


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


def assigned(kwargs: dict) -> list[int]:
    """The sentence numbers a review request assigns to its call: "3 to 6", or
    "2, 5, 9" when they are not consecutive (a second review)."""
    numbers = re.search(r"Your assignment: sentences ([\d, to]+)\.", kwargs["messages"][-1]["content"]).group(1)
    if " to " in numbers:
        first, last = numbers.split(" to ")
        return list(range(int(first), int(last) + 1))
    return [int(number) for number in numbers.split(", ")]


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


def fixes_reply(replace: dict | None = None, delete=()) -> str:
    """A targeted-fix answer: replacements {sentence number: marked text} and deletions."""
    fixes = [f'<fix sentence="{n}">{text}</fix>' for n, text in (replace or {}).items()]
    fixes += [f'<fix sentence="{n}" delete="true"/>' for n in delete]
    return "<fixes>\n" + "\n".join(fixes) + "\n</fixes>"


def answer_pipeline(claude, drafts, reviews=(), trim=None, fixes=None, structure=ARCHETYPE_GENERAL) -> list[str]:
    """Make the fake model play every call of a single-writer run, whatever
    order the parallel review calls arrive in.

    drafts: what each draft call returns, in order (the draft, then a full
    redraft), put in the output envelope unless it has one. A draft call with
    none left fails the test: there is never a third draft. fixes: the
    targeted-fix call's reply; a targeted-fix call without one fails the test.
    reviews: one dict per review pass (before and after the fix or redraft),
    {changes, rhythm, replace} as answer_groups takes them; a pass with no dict
    gets benign records. trim: the trim call's reply; a trim call without one
    fails the test. Returns the list the drafter's prompts are appended to, in order.
    """
    drafts, prompts = list(drafts), []

    def reply(kwargs):
        tool = (kwargs.get("tool_choice") or {}).get("name")
        if tool == "choose_post_type":
            return structure
        if tool == "rank_sentences_to_delete":
            assert trim is not None, "an unexpected trim call"
            return trim
        if tool == "record_review":
            spec = reviews[len(prompts) - 1] if len(prompts) - 1 < len(reviews) else {}
            group = assigned(kwargs)
            override = (spec.get("replace") or {}).get(group[0])
            if isinstance(override, BaseException):
                raise override
            if override is not None:
                return override
            notes = [note for n, note in (spec.get("rhythm") or {}).items() if n in group]
            return review_reply(group, spec.get("changes"), notes)
        prompt = kwargs["messages"][-1]["content"]
        prompts.append(prompt)
        if "<post_sentences>" in prompt:
            assert fixes is not None, "an unexpected targeted-fix call"
            return fixes
        assert drafts, "a draft call with no draft left to return: a third draft?"
        return enveloped(drafts.pop(0))
    claude.respond_with(reply)
    return prompts
