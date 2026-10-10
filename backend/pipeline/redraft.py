"""What variant B does with what the checks and the review found. No model calls.

Three decisions, all in code:
- which issues act (trigger the one redraft) and which are recorded only;
- what the redraft is told about each acting issue: a fixed instruction for its
  type and quoted material, never anything a model wrote about the draft;
- how the run ended (clean, fixed, issues_remain, not_reviewed).

REDRAFT_RULES is the one table. An issue type acts when it has a row there; its
row is the instruction the redraft gets and the fields of the issue it is
shown. A type with no row must be listed in RECORD_ONLY, or the run fails: a
new issue type is never silently ignored or silently acted on.

The record this builds is state["review"]:
    first      {checks, acting, recorded}: the first draft's issues, split
    redraft    {entries, downgraded_from?, ...}: only when a redraft ran; the
               entries are exactly what the redraft prompt listed
               (agents.draft_agent.redraft_node adds the call's tokens)
    redraft_truncated  {max_tokens, output_tokens}: only when the redraft was
               cut off at its output limit; the first draft is then returned
    second     {checks, acting, recorded}: the redraft's issues, before any trim
    remaining  acting issues on the post that is returned (after any trim)
    unreviewed sentences of the returned post with no valid review record
    outcome    clean | fixed | issues_remain | not_reviewed

The outcome describes the post that is returned. It is not_reviewed only when
some sentence of that post has no valid review record; a first review that
failed does not make it so when a redraft followed and its review covered
every sentence.
The review model's own answers are state["review_first"] and state["review_second"].
"""

import logging
from dataclasses import dataclass
from typing import Any, Callable

from pipeline.checks import REQUEST
from pipeline.state import PipelineState
from utils.citations import escape_markers
from utils.formatters import GENERAL_ARCHETYPE, STORY_ARCHETYPES

logger = logging.getLogger(__name__)

Line = tuple[str, str]                      # (label, value) as shown in the redraft prompt

# Derived and stored in the trace; they never trigger a redraft.
# Decided 2026-10-09 from the 6a-4 live check (docs/plans/single-writer.md,
# section 5): changed_detail was right on 3 of 12, arguable on 3 and wrong on 6
# (synonyms, rewordings, punctuation); ai_rhythm was 9 of the 18 issues on the
# two drafts, mostly judgement calls. Acting on either would spend the one
# redraft on a false positive about half the time. Revisit after the ablation,
# with a stronger review model.
RECORD_ONLY = ("changed_detail", "ai_rhythm")

_NOWHERE = "nowhere"
_THE_REQUEST = "the request"
# What wrong_attribution found, from the source index (never from model prose).
_ORIGINS = {"external": "a source the author read", "self": "the author's own source", "none": "no source states it"}
# What banned_text found (pipeline.checks.banned_text).
_BANNED = {"em_dash": "an em dash", "word_to_avoid": "a word the author avoids",
           "placeholder_in_first_post": "a [DIAGRAM: ...] or [IMAGE: ...] line in a first post"}


def _places(ids: list[str]) -> str:
    return ", ".join(_THE_REQUEST if sid == REQUEST else sid for sid in ids)


def _text(issue: dict) -> list[Line]:
    return [("Text", issue["text"])] if issue["text"] else []


def _sources(label: str) -> Callable[[dict], list[Line]]:
    return lambda issue: [(label, _places(issue["sources"]))] if issue["sources"] else []


def _detail(key: str, label: str) -> Callable[[dict], list[Line]]:
    """One field of the issue's detail: a list of ids, a number, or words of the post."""
    def lines(issue: dict) -> list[Line]:
        value = issue["detail"].get(key)
        if value is None or value == []:
            return []
        return [(label, _places(value) if isinstance(value, list) else str(value))]
    return lines


def _found_in(issue: dict) -> list[Line]:
    return [("Found in", _places(issue["detail"]["found_in"]) or _NOWHERE)]


def _evidence(issue: dict) -> list[Line]:
    """The source's own words, written as the sources block writes a source:
    no tag it contains can close the problems block, and no marker in it is live."""
    if not issue.get("evidence"):
        return []
    return [("Source words", escape_markers(issue["evidence"].replace("<", "&lt;")))]


def _origin(issue: dict) -> list[Line]:
    origin = _ORIGINS[issue["detail"]["authorship"]]
    return [("Stated by", f"{_places(issue['sources'])} ({origin})" if issue["sources"] else origin)]


def _banned(issue: dict) -> list[Line]:
    found = _BANNED[issue["detail"]["kind"]]
    word = issue["detail"].get("word")
    return [("Not allowed", f"{found}: {word}" if word else found)]


@dataclass(frozen=True)
class RedraftRule:
    instruction: str                                    # fixed text; the same for every issue of the type
    material: tuple[Callable[[dict], list[Line]], ...]  # the quoted fields of the issue the entry shows


# The one table: every issue type that triggers the redraft, with what the
# redraft is told. Deterministic check types first (pipeline.checks.ISSUE_TYPES),
# then review types (pipeline.review_rules.ISSUE_TYPES). under_length is not an
# issue type at all: nothing ever lengthens a post. No instruction asks for
# anything to be added, and each one allows leaving the text out.
REDRAFT_RULES: dict[str, RedraftRule] = {
    "citation_malformed": RedraftRule(
        "This text is not a valid marker. End the sentence it belongs to with exactly one marker, "
        "in one of the forms the citation rules give.",
        (_text,)),
    "citation_unknown_id": RedraftRule(
        "This text cites an id that is not in <sources>. Cite the source that states it. If no source "
        "and no part of the request states it, leave it out.",
        (_text, _detail("unknown", "Not in <sources>"))),
    "uncited_span": RedraftRule(
        "This text has no marker. End each of its sentences with the marker that says where it comes "
        "from. If no source and no part of the request states a fact in it, leave that fact out.",
        (_text,)),
    "specific_not_in_cited_source": RedraftRule(
        'The sources this text cites do not state the specific quoted below. If "Found in" names a '
        "source or the request, cite that for the sentence that carries the specific. If it says "
        "nowhere, leave the specific out.",
        (_text, _sources("Cites"), _detail("specific", "Specific"), _found_in)),
    "view_contains_specific": RedraftRule(
        'This text is marked [[V]], and a [[V]] sentence states no fact. If "Found in" names a source '
        "or the request, cite that instead of [[V]]. If it says nowhere, leave the specific out.",
        (_text, _detail("specific", "Specific"), _found_in)),
    "event_unverified": RedraftRule(
        "The EVENT line could not be checked against one of the author's own sources. Write this post "
        "to the structure given above, with no EVENT line. Tell nothing as something that happened to "
        "the author unless a source whose kind begins OWN EXPERIENCE states it.",
        (_text,)),
    "mixed_authorship_span": RedraftRule(
        "This text cites one of the author's own sources together with a source the author read. Give "
        "the author's own point and the source's point in separate sentences, each with its own marker.",
        (_text, _detail("self", "The author's own"), _detail("external", "Read by the author"))),
    "over_length": RedraftRule(
        "The post is longer than its maximum. Leave out whole sentences, the ones the post loses "
        "least by, until it is within the length given above. Add nothing.",
        (_detail("words", "Words"), _detail("max_words", "Maximum"))),
    "banned_text": RedraftRule(
        "This text contains something the post must not contain, named below. Write the sentence without it.",
        (_text, _banned)),
    "not_in_sources": RedraftRule(
        'No source and no part of the request states this. If "Words nothing states" is given, leave '
        "those words out and keep the rest. Otherwise leave the sentence out. Put no other fact, "
        "feeling or reason in its place.",
        (_text, _detail("unsupported_part", "Words nothing states"))),
    "wrong_citation": RedraftRule(
        'The place named after "Stated by" states this, and the sentence\'s marker points somewhere '
        "else. Keep the sentence's words and change its marker to that place.",
        (_text, _detail("supported_by", "Stated by"), _evidence)),
    "wrong_attribution": RedraftRule(
        "This sentence presents its content as coming from the wrong place. What a source whose kind "
        "begins OWN EXPERIENCE states is the author's own, and is told as the author's own. What any "
        "other source states is told as what that source says, never as something the author did, saw "
        "or felt. Nothing is credited to a source that does not state it. Write the sentence so that "
        "it follows this, or leave it out.",
        (_text, _origin, _evidence)),
    "cross_source_link": RedraftRule(
        "This sentence links facts from different sources as cause, sequence or result, and no source "
        "states that link. State the facts in separate sentences, each with its own marker and with "
        "nothing linking them, or leave the link out.",
        (_text, _sources("Sources linked"))),
    "off_topic": RedraftRule(
        "This sentence leaves the topic. Leave it out, together with anything that only follows from "
        "it. Put nothing in its place that no source states.",
        (_text,)),
}


def split_issues(checks: dict, review: dict) -> tuple[list[dict], list[dict]]:
    """(acting, recorded) issues of one draft: the checks' issues, then the
    review's, each tagged with its origin. A review that did not happen
    contributes none, so the deterministic issues still act."""
    acting, recorded = [], []
    tagged = [*({**issue, "origin": "checks"} for issue in checks["issues"]),
              *({**issue, "origin": "review"} for issue in review["issues"])]
    for issue in tagged:
        if issue["type"] in REDRAFT_RULES:
            acting.append(issue)
        elif issue["type"] in RECORD_ONLY:
            recorded.append(issue)
        else:
            raise ValueError(f"issue type {issue['type']!r} has no redraft rule and is not record-only")
    return acting, recorded


def issue_entries(acting: list[dict]) -> list[dict[str, Any]]:
    """One entry per acting issue, as the redraft prompt lists it: {type,
    instruction, material: [[label, value], ...]}. Everything in it is the
    type's fixed instruction or a field of the issue chosen by the type's rule."""
    entries = []
    for issue in acting:
        rule = REDRAFT_RULES[issue["type"]]
        material = [list(line) for lines in rule.material for line in lines(issue)]
        entries.append({"type": issue["type"], "instruction": rule.instruction, "material": material})
    return entries


def decide_node(state: PipelineState) -> PipelineState:
    """After the first review: split the first draft's issues and, when any
    acts, prepare the one redraft.

    A story whose event could not be verified is to be redrafted to the General
    structure: that is recorded here (downgraded_from) and applied by
    apply_downgrade when the redraft is written.
    """
    checks = state["checks_before_trim"]
    acting, recorded = split_issues(checks, state["review_first"])
    record: dict[str, Any] = {"first": {"checks": checks, "acting": acting, "recorded": recorded}}
    if acting:
        record["redraft"] = {"entries": issue_entries(acting)}
        chosen = state.get("archetype", "")
        if chosen in STORY_ARCHETYPES and any(issue["type"] == "event_unverified" for issue in acting):
            record["redraft"]["downgraded_from"] = chosen
        logger.info("decide: redraft for %s", sorted({issue["type"] for issue in acting}))
    state["review"] = record
    return state


def apply_downgrade(state: PipelineState) -> None:
    """Make the post a General Post when decide_node recorded that its event
    could not be verified. Does nothing otherwise."""
    chosen = state["review"]["redraft"].get("downgraded_from")
    if chosen is None:
        return
    state["archetype"] = GENERAL_ARCHETYPE
    state["archetype_decision"] = {
        **(state.get("archetype_decision") or {}),
        "archetype": GENERAL_ARCHETYPE, "downgraded_from": chosen,
        "reason": "the draft's event could not be verified",
    }


def route_after_decide(state: PipelineState) -> str:
    return "redraft" if "redraft" in state["review"] else "outcome"


def outcome_node(state: PipelineState) -> PipelineState:
    """How the run ended, for the post that is returned.

    Does nothing when no review ran (quality="draft"). The returned post is the
    redraft, or the first draft when there was no redraft or the redraft was
    cut off; its review is the last one that ran on it. After a redraft was
    attempted, the remaining issues are the final checks' acting issues plus
    that review's acting issues whose sentence the trim did not delete. The
    post is not_reviewed when a sentence still in it has no valid review record.
    """
    record = state.get("review")
    if record is None:
        return state
    second_review = state.get("review_second")
    review = second_review or state["review_first"]
    # The trim numbers sentences as the review does (utils.sentences.split_spans).
    deleted = {entry["index"] for entry in (state.get("trim_result") or {}).get("deleted", [])}
    remaining: list[dict] = []
    if second_review is not None:
        acting, recorded = split_issues(state["checks_before_trim"], second_review)
        record["second"] = {"checks": state["checks_before_trim"], "acting": acting, "recorded": recorded}
    if "redraft" in record:
        reviewed_acting, _ = split_issues({"issues": []}, review)
        final_acting, _ = split_issues(state["checks_final"], {"issues": []})
        remaining = [*final_acting, *(issue for issue in reviewed_acting if issue["sentence"] not in deleted)]
    unreviewed = [position for position in review["unreviewed"] if position not in deleted]
    if unreviewed:
        outcome = "not_reviewed"
    elif "redraft" not in record:
        outcome = "clean"
    else:
        outcome = "issues_remain" if remaining else "fixed"
    record["remaining"] = remaining
    record["unreviewed"] = [review["sentences"][position]["text"] for position in unreviewed]
    record["outcome"] = outcome
    logger.info("review outcome: %s (%d acting issue(s) on the returned post)", outcome, len(remaining))
    return state


def review_summary(state: PipelineState) -> dict[str, Any] | None:
    """What /generate returns about the review: the outcome and the acting
    issues on the returned post. None when no review ran."""
    record = state.get("review")
    if record is None or "outcome" not in record:
        return None
    return {"outcome": record["outcome"],
            "issues": [{"type": issue["type"], "sentence_text": issue["text"]} for issue in record["remaining"]]}
