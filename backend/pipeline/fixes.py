"""Variant B's fixes to a reviewed draft: what code changes itself, which path
the remaining issues take, and how a model's targeted fixes are applied. No
model calls.

Order, after the first review found acting issues:

1. Fixes made in code (code_fix_node), with no model:
   - not_in_sources on a whole sentence (no unsupported_part, or one that is
     the whole sentence): the sentence is deleted, by the same code that
     deletes sentences for the trim;
   - wrong_citation: the sentence's marker is replaced with the place the
     review found (its supported_by); its words do not change.
   The post is then finalised and checked again, in code. A deletion can
   leave the next sentence leaning on words that are gone, so the sentence
   that follows each run of deleted sentences becomes an after_deletion repair:
   not an issue, but a sentence the targeted fix is asked to look at.

2. The routing rule (choose_route), on the issues that are left:
   - "full"      an issue whose scope is the post: the event could not be
                 verified, or the post is still over its maximum. The one full
                 redraft deals with it and with every other remaining issue.
   - "targeted"  otherwise, when a sentence still has an issue or follows a
                 deletion: one drafter call returns replacements for those
                 sentences only.
   - "none"      nothing is left for a model.
   One path at most: a targeted fix and a full redraft never both run, and
   neither runs twice.

3. Targeted fixes (apply_targeted_fixes): the model's <fix> entries are
   validated and spliced in. A fix counts only for a sentence that was flagged,
   given exactly once, and (for a replacement) made of cited sentences with
   valid markers. Any other fix is rejected and recorded, and its sentence
   stays as it was, so its issue remains. No other sentence can change. A
   replacement that is the sentence as it was changes nothing ("unchanged"),
   and a sentence flagged only as a repair cannot be deleted.

Sentences are the post's spans cut by utils.sentences.split_spans, the same
numbering the review and the trim use. After step 1 the post's spans are its
sentences; a check issue is placed on the sentence its span became.

state["review"]["fixes"]:
    code      [{type: sentence_deleted | marker_replaced, issue, sentence, before, after}]
              sentence is 0-based in the first draft; before and after are the
              sentence with its marker (after is None for a deletion)
    origin    for each sentence of the post now, the first-draft sentence it is
              (0-based), or None for one a model wrote. The second review
              reuses the first review's record for every sentence that has one.
    unplaced  remaining issues about no one sentence, which no targeted fix can reach
    repairs   the after_deletion repairs, [{type, at, text, detail: {removed, before}}]
    route     "full" | "targeted" | "none"
state["review"]["targeted"] (targeted path only):
    entries   the problems as the prompt listed them, each with its sentence number
    flagged   the 1-based numbers of the sentences that may be fixed
    repair_only  those flagged only as a repair: they may be reworded, not deleted
    applied   [{sentence, before, after}]   (after is None for a deletion)
    unchanged the numbers whose fix returned the sentence as it was
    invalid   [{sentence, reason, text}]    rejected fixes
    format_failures, truncated?, input_tokens, output_tokens
state["review"]["removed"]: content taken out because nothing states it,
    [{kind, text, how: deleted | trimmed, by: code | model}]; kind is what the
    review said the sentence mainly was (feeling_or_reaction, motive, ...).
"""

import logging
from pipeline.checks import REQUEST, run_checks
from pipeline.finalise import finalise_marked, settle
from pipeline.redraft import REDRAFT_RULES, issue_entries, split_issues
from pipeline.state import PipelineState
from utils.citations import Span, delete_spans, marker, replace_span
from utils.draft_output import parse_fixes
from utils.formatters import STORY_ARCHETYPES
from utils.sentences import split_spans
from utils.wording import same_sentence

logger = logging.getLogger(__name__)


def _marked(sentence: Span) -> str:
    return f"{sentence.text} {marker(sentence)}".rstrip()


def _units(state: PipelineState) -> list[tuple[int, Span]]:
    """The post's sentences as (position of the span it is in, sentence)."""
    return split_spans([Span.from_dict(c) for c in state.get("citations") or []])


def _recheck(state: PipelineState) -> None:
    """The deterministic checks on the post as it now stands (both check records)."""
    leftover = (state.get("final_validation") or {}).get("leftover_markers") or []
    state["checks_before_trim"] = state["checks_final"] = run_checks(state, leftover)


def _sentence_of(issue: dict, units: list[tuple[int, Span]]) -> int | None:
    """The sentence a check issue is about: the first sentence of its span, or
    the sentence a leftover marker stands in. None when it is about none."""
    if issue["span"] is not None:
        return next((i for i, (position, _) in enumerate(units) if position == issue["span"]), None)
    start = issue["detail"].get("start")
    if issue["type"] == "citation_malformed" and start is not None:
        return next((i for i, (_, s) in enumerate(units) if s.start <= start <= s.end), None)
    return None


def _content_kinds(state: PipelineState) -> dict[int, str]:
    """first-draft sentence (0-based) -> what the first review said it mainly is."""
    return {record["sentence"] - 1: record["content"] for record in state["review_first"]["records"]}


# ── 1. Fixes made in code ─────────────────────────────────────────────────────

def _cited_as(supported_by: list[str]) -> tuple[str, tuple[str, ...]]:
    """The citation that points where the review found the sentence stated: the
    sources when any source states it, the request otherwise (a marker names
    one or the other)."""
    sources = tuple(sid for sid in supported_by if sid != REQUEST)
    return ("sources", sources) if sources else ("request", ())


def _whole_sentence(issue: dict, sentence: Span) -> bool:
    """Whether a not_in_sources issue is about the whole sentence: the review
    named no part of it, or named all of it (utils.wording.same_sentence)."""
    part = issue["detail"].get("unsupported_part")
    return not part or same_sentence(part, sentence.text)


def _repairs(sentences: list[Span], delete: set[int], now_at: dict[int, int]) -> list[dict]:
    """One after_deletion repair for the sentence that follows each run of
    deleted sentences, when there is one and it can still be placed."""
    repairs = []
    for position in sorted(delete):
        if position - 1 in delete:
            continue                                         # not the start of a run
        end = position
        while end + 1 in delete:
            end += 1
        if now_at.get(end + 1) is None:
            continue                                         # the run ends the post
        removed = " ".join(sentences[i].text for i in range(position, end + 1))
        before = sentences[position - 1].text if position else None
        repairs.append({"type": "after_deletion", "origin": "fix", "at": now_at[end + 1], "span": None,
                        "text": sentences[end + 1].text, "sources": [], "evidence": None,
                        "detail": {"removed": removed, "before": before}})
    return repairs


def code_fix_node(state: PipelineState) -> PipelineState:
    """Make the fixes that need no model, check the post again, and choose the
    path for what is left (see the module docstring)."""
    record = state["review"]
    sentences = [sentence for _, sentence in _units(state)]
    review_issues = [issue for issue in record["first"]["acting"] if issue["origin"] == "review"]
    delete = {issue["sentence"] for issue in review_issues
              if issue["type"] == "not_in_sources" and _whole_sentence(issue, sentences[issue["sentence"]])}
    fixes, removed, edited = [], [], list(sentences)
    for issue in review_issues:
        position, before = issue["sentence"], sentences[issue["sentence"]]
        if issue["type"] == "not_in_sources" and position in delete:
            fixes.append({"type": "sentence_deleted", "issue": issue["type"], "sentence": position,
                          "before": _marked(before), "after": None})
            removed.append({"kind": issue["detail"]["content"], "text": before.text, "how": "deleted", "by": "code"})
        elif issue["type"] == "wrong_citation" and position not in delete:
            basis, sources = _cited_as(issue["detail"]["supported_by"])
            edited[position] = Span(before.start, before.end, before.text, basis, sources)
            fixes.append({"type": "marker_replaced", "issue": issue["type"], "sentence": position,
                          "before": _marked(before), "after": _marked(edited[position])})
    text, kept = delete_spans(state["current_draft"], edited, delete)
    settle(state, text, kept)
    _recheck(state)
    # Each sentence of the post now, and the first-draft sentence it is. A kept
    # sentence the segmenter now cuts differently is no longer known to be one.
    survivors = [position for position in range(len(sentences)) if position not in delete]
    units = _units(state)
    per_span = [sum(1 for position, _ in units if position == i) for i in range(len(kept))]
    origin = [survivors[position] if per_span[position] == 1 else None for position, _ in units]

    # What is left: the checks' issues on the post as it now stands, and the
    # first review's issues that no code fix dealt with, renumbered.
    now_at = {was: now for now, was in enumerate(origin) if was is not None}
    check_issues, _ = split_issues(state["checks_final"], {"issues": []})
    for issue in check_issues:
        issue["at"] = _sentence_of(issue, units)
    left = [{**issue, "at": now_at.get(issue["sentence"])} for issue in review_issues
            if issue["sentence"] not in delete and issue["type"] != "wrong_citation"]
    remaining = [*check_issues, *left]
    repairs = _repairs(sentences, delete, now_at)
    route = choose_route([*remaining, *repairs])
    record["fixes"] = {"code": fixes, "origin": origin, "route": route, "repairs": repairs,
                       "unplaced": [issue for issue in remaining if issue["at"] is None and route != "full"]}
    record["removed"] = removed
    if route == "full":
        record["redraft"] = {"entries": issue_entries(remaining)}
        chosen = state.get("archetype", "")
        if chosen in STORY_ARCHETYPES and any(issue["type"] == "event_unverified" for issue in remaining):
            record["redraft"]["downgraded_from"] = chosen
    elif route == "targeted":
        with_issue = {issue["at"] + 1 for issue in remaining if issue["at"] is not None}
        placed = sorted((issue for issue in [*remaining, *repairs] if issue["at"] is not None),
                        key=lambda issue: issue["at"])
        record["targeted"] = {"entries": issue_entries(placed, numbered=True),
                              "flagged": sorted({issue["at"] + 1 for issue in placed}),
                              "repair_only": sorted({issue["at"] + 1 for issue in repairs} - with_issue),
                              "parts": {str(issue["at"] + 1): issue["detail"]["unsupported_part"] for issue in placed
                                        if issue["type"] == "not_in_sources"}}
    logger.info("fixes: %d in code, then %s", len(fixes), route)
    return state


# ── 2. The routing rule ───────────────────────────────────────────────────────

def choose_route(remaining: list[dict]) -> str:
    """Which single path the issues left after the code fixes take.

    remaining: acting issues and after_deletion repairs, each with "at": the
    sentence it is about, or None.
    """
    if any(REDRAFT_RULES[issue["type"]].scope == "post" for issue in remaining):
        return "full"            # event_unverified, or still over the maximum
    if any(issue["at"] is not None for issue in remaining):
        return "targeted"
    return "none"


def route_after_fix(state: PipelineState) -> str:
    return state["review"]["fixes"]["route"]


# ── 3. Targeted fixes ─────────────────────────────────────────────────────────

def _replacement(marked: str) -> tuple[str, list[Span]] | str:
    """(clean text, its sentences) for a replacement, or why it cannot be used."""
    finalised, stripped = finalise_marked(marked.strip(), None)
    if stripped.failures:
        return f"marker_failure: {[failure.kind for failure in stripped.failures]}"
    if not stripped.spans:
        return "empty"
    if any(span.basis == "uncited" for span in stripped.spans):
        return "uncited_text"
    return finalised.text, [sentence for _, sentence in split_spans(stripped.spans)]


def _is_unchanged(before: Span, after: list[Span]) -> bool:
    """Whether a replacement is the sentence as it was: the same words
    (whitespace aside) and the same citation."""
    if len(after) != 1:
        return False
    return (" ".join(after[0].text.split()), after[0].basis, after[0].sources) == (
        " ".join(before.text.split()), before.basis, before.sources)


def apply_targeted_fixes(state: PipelineState, answer: str, *, truncated: bool) -> None:
    """Validate the model's fixes and splice the valid ones into the post.

    A fix is rejected (and recorded in targeted.invalid, its sentence left as
    it was) when its sentence was not flagged ("not_flagged"), when the
    sentence is given more than once ("repeated"), when its replacement is
    empty, has uncited text or has a marker that is not valid, or when it
    deletes a sentence flagged only as a repair ("delete_not_allowed"). A
    flagged sentence with no fix is recorded as "missing". A replacement that
    is the sentence as it was, marker included, is recorded as unchanged and
    nothing is done: the sentence keeps its review record. A truncated answer
    is not read at all. Sentences nobody flagged are never touched.
    """
    record, targeted = state["review"], state["review"]["targeted"]
    sentences, origin = [sentence for _, sentence in _units(state)], record["fixes"]["origin"]
    flagged = set(targeted["flagged"])
    fixes, failures = ([], [{"kind": "truncated", "text": ""}]) if truncated else parse_fixes(answer)
    applied, invalid, unchanged = [], [], []
    targeted.update(applied=applied, invalid=invalid, unchanged=unchanged, format_failures=failures)

    by_number: dict[int, list] = {}
    for fix in fixes:
        by_number.setdefault(fix.sentence, []).append(fix)
    edits: dict[int, tuple[str, list[Span]] | None] = {}     # 0-based sentence -> replacement, or None to delete
    for number, given in by_number.items():
        shown = given[0].text or ""
        if number not in flagged:
            invalid.append({"sentence": number, "reason": "not_flagged", "text": shown})
        elif len(given) > 1:
            invalid.append({"sentence": number, "reason": "repeated", "text": shown})
        elif given[0].text is None:
            if number in targeted["repair_only"]:
                invalid.append({"sentence": number, "reason": "delete_not_allowed", "text": ""})
            else:
                edits[number - 1] = None
        else:
            replacement = _replacement(given[0].text)
            if isinstance(replacement, str):
                invalid.append({"sentence": number, "reason": replacement, "text": shown})
            elif _is_unchanged(sentences[number - 1], replacement[1]):
                unchanged.append(number)
            else:
                edits[number - 1] = replacement
    invalid += [{"sentence": number, "reason": "missing", "text": ""} for number in sorted(flagged - set(by_number))]
    if not edits:
        logger.warning("targeted fixes: none applied (%s)", [item["reason"] for item in invalid] or failures)
        return

    kinds = _content_kinds(state)
    text, spans = state["current_draft"], list(sentences)
    # slots[i]: which sentence of the post before the fixes spans[i] is, or None for new text.
    slots: list[int | None] = list(range(len(sentences)))
    for position in sorted(edits, reverse=True):             # last first: earlier positions stay valid
        before, edit = sentences[position], edits[position]
        kind = kinds.get(origin[position]) if origin[position] is not None else None
        if edit is None:
            applied.append({"sentence": position + 1, "before": _marked(before), "after": None})
            record["removed"].append({"kind": kind, "text": before.text, "how": "deleted", "by": "model"})
            continue
        new_text, new_sentences = edit
        text, replaced = replace_span(text, spans, position, new_text, new_sentences)
        spans = list(replaced)
        slots[position:position + 1] = [None] * len(new_sentences)
        applied.append({"sentence": position + 1, "before": _marked(before),
                        "after": " ".join(_marked(sentence) for sentence in new_sentences)})
        part = targeted["parts"].get(str(position + 1))
        if part and " ".join(part.split()) not in " ".join(new_text.split()):
            record["removed"].append({"kind": kind, "text": part, "how": "trimmed", "by": "model"})
    applied.reverse()
    gone = {i for i, slot in enumerate(slots) if slot is not None and slot in edits}     # the deletions
    text, kept = delete_spans(text, spans, gone)
    record["fixes"]["origin"] = [None if slot is None else origin[slot] for i, slot in enumerate(slots) if i not in gone]
    settle(state, text, kept)
    _recheck(state)
