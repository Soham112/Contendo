"""Final fact check: every claim in the finished post, judged against its sources.

Runs after word_count_enforcer, before finalize. One Haiku call reads the post
as numbered sentences and lists only the unsupported claims (events,
statistics, and in no-specifics mode names), [] when everything is supported.
Only when something is unsupported: one Sonnet call rewrites those sentences
into opinions or general observations (no new facts), one Haiku call re-checks
them, and any that still fail are removed.

Allowed sources:
- first-person and other events: self-authored chunks and the request (topic +
  context); in no-specifics mode only the request
- statistics and "research says" claims: any chunk and the request
- who the author is (name, role, employer): identity facts, normal mode only
- in no-specifics mode, any name not in the topic or context is unsupported

The regex specifics guard (utils/specifics.py) still checks numbers, dates,
durations and money at every step; this node judges meaning, which a pattern
list can't.

Enforced only in no-specifics mode (or normal mode when
config.fact_check.FACT_CHECK_ENFORCE_NORMAL_MODE is on). Otherwise it is
log-only: log_fact_check runs after the response and writes the flags to the
trace, changing nothing (see enforced() for why this is a stopgap).

Never breaks the pipeline: on any error the post is left as it is and the
error is recorded in state["fact_check"].
"""

import json
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel

from config import fact_check as cfg
from utils.specifics import Specific, remove_sentences
from llm.client import HAIKU, SONNET, complete, complete_structured
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from utils.frames import chunk_field, is_self_authored

logger = logging.getLogger(__name__)

FACT_CHECK_PROMPT = """You are a fact checker for a LinkedIn post written in the author's voice. Find the claims in the post that the allowed sources do not support. Do not judge style or quality.

Post, one sentence per line, numbered:
<post>
{numbered}
</post>

Allowed sources:

SELF-AUTHORED NOTES (the author's own experiences; the only notes that can support a first-person event):
{self_notes}

OTHER SOURCES (articles, videos and other material the author read or saved; can support general and "research says" claims, never a first-person event):
{other_sources}

THE REQUEST (what the author typed; supports only what it explicitly states. A topic that names a subject, such as "my favourite trails" or "my experience at X", states no event: it does not support any specific thing that happened):
Topic: {topic}
Context: {context}

AUTHOR IDENTITY (supports only who the author is, never what happened to them):
{identity}

What to check:
- event: something presented as having happened, to the author ("I watched...", "my legs gave out", "we shipped") or to a specific person, team, company or customer. Supported only if the self-authored notes or the request describe that same specific event (what happened, and to whom). A topic or context that only implies the author has done something in general does not support a specific incident.{no_specifics_rule}
- statistic: a number, measurement, research finding, or specific factual claim about the world ("research shows...", "agents loop when tools change"). Supported if any source states it, in any wording.
- A statement of who the author is (name, role, employer) is supported by the author identity.
- Paraphrase is fine. A changed number, name, place, time or outcome is not supported.
- Never flag opinions: views, arguments, recommendations, predictions, hypotheticals, or widely known general statements with no numbers, named studies or specific outcomes.

Use the record_fact_check tool to return the unsupported claims in flagged.
Each claim has i (sentence number), type (event, statistic or name), and why (under 10 words).
Return an empty flagged list when everything is supported."""

_NO_SPECIFICS_RULE = (
    " This is an opinion post without specifics: only the request can support an event, "
    "never the notes or the identity.\n"
    "- name: in this mode, any named place, person, organisation, product or trail that is not in the "
    "topic or context is unsupported, even when the name is real (for example \"Acme Corp\" in a post "
    "on the topic \"Startup hiring mistakes\")."
)

REWRITE_PROMPT = """Rewrite each sentence below so it makes no unsupported factual claim. Turn it into an opinion or a general observation in the same voice, or drop the unsupported part. Add no new facts: no numbers, names, places, times, events or results. Keep the same point, so it still fits where it sits in the post.

Post (context only; do not rewrite it):
<post>
{post}
</post>

Sentences to rewrite:
{sentences}

Return ONLY a JSON array of strings, one rewrite per sentence, in the same order. No prose, no markdown fences."""


def _parse_json_array(raw: str) -> list:
    """Direct parse, then fenced, then the first [...] span. Raises ValueError."""
    attempts = [
        lambda r: json.loads(r),
        lambda r: json.loads(r.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()),
        lambda r: json.loads(re.search(r"\[.*\]", r, re.DOTALL).group()),
    ]
    for attempt in attempts:
        try:
            value = attempt(raw)
            if isinstance(value, list):
                return value
        except Exception:
            continue
    raise ValueError(f"no JSON array in fact-check response: {raw[:200]!r}")


def _identity(state: PipelineState) -> str:
    """Name, role and employers (work experience nodes). Normal mode only."""
    if state.get("no_specifics"):
        return "none (not allowed in this mode)"
    profile = state.get("profile") or {}
    employers = sorted({
        n.get("entity_name", "") for n in state.get("experience_nodes") or []
        if n.get("node_type") == "work" and n.get("entity_name")
    })
    lines = [f"Name: {profile.get('name') or 'unknown'}", f"Role: {profile.get('role') or 'unknown'}"]
    if employers:
        lines.append("Employers: " + ", ".join(employers))
    return "\n".join(lines)


def _source_sections(state: PipelineState) -> tuple[str, str]:
    profile = state.get("profile") or {}
    chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])
    own, other = [], []
    for chunk in chunks:
        text = chunk_field(chunk, "text") or chunk_field(chunk, "content")
        (own if is_self_authored(chunk, profile) else other).append(text)
    if state.get("no_specifics"):
        own = []  # notes can't support events in this mode; other sources stay for statistics
    fmt = lambda texts: "\n---\n".join(texts) if texts else "none"
    return fmt(own), fmt(other)


def _split_sentences(post: str) -> list[str]:
    """The post's sentences, in order, exactly as written (numbered for the judge)."""
    return [s.strip() for line in post.splitlines()
            for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]


class UnsupportedClaim(BaseModel):
    i: int
    type: Literal["event", "statistic", "name"]
    why: str


class FactCheckResult(BaseModel):
    flagged: list[UnsupportedClaim]


def _judge(post: str, state: PipelineState, user_id: str, event_type: str) -> list[dict[str, Any]]:
    """Unsupported claims only: [{i, sentence, type, why}]. [] when all supported."""
    sentences = _split_sentences(post)
    self_notes, other_sources = _source_sections(state)
    result = complete_structured(
        schema=FactCheckResult,
        tool_name="record_fact_check",
        tool_description="Record unsupported claims in the final post.",
        model=HAIKU,
        max_tokens=400,
        messages=[{"role": "user", "content": FACT_CHECK_PROMPT.format(
            numbered="\n".join(f"{n}. {s}" for n, s in enumerate(sentences, 1)),
            self_notes=self_notes,
            other_sources=other_sources,
            topic=state.get("topic", ""),
            context=(state.get("context") or "").strip() or "none",
            identity=_identity(state),
            no_specifics_rule=_NO_SPECIFICS_RULE if state.get("no_specifics") else "",
        )}],
        user_id=user_id,
        event_type=event_type,
    )
    flagged, seen = [], set()
    for claim in result.flagged:
        item = claim.model_dump()
        try:
            i = int(item.get("i"))
        except (AttributeError, TypeError, ValueError):
            continue
        if 1 <= i <= len(sentences) and i not in seen:
            seen.add(i)
            flagged.append({"i": i, "sentence": sentences[i - 1],
                            "type": str(item.get("type", "")).strip().lower(),
                            "why": str(item.get("why", "")).strip()})
    return flagged


def _replace_sentence(post: str, old: str, new: str) -> str:
    if old in post:
        return post.replace(old, new, 1)
    # The model may copy a sentence with small differences: match on word overlap.
    old_words = set(old.lower().split())
    best, best_overlap = None, 0
    for line in post.splitlines():
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            overlap = len(old_words & set(sentence.lower().split()))
            if overlap > best_overlap:
                best, best_overlap = sentence, overlap
    if best and best_overlap >= max(2, len(old_words) // 2):
        return post.replace(best, new, 1)
    return post


def enforced(state: PipelineState) -> bool:
    """Whether this run's fact check may change the post.

    STOPGAP: normal-mode fact check is log-only because the find-prompt
    over-flags paraphrases of the sources (0/5 on supported claims, 2026-10-03).
    Proper fix: citation-based drafting (each sentence tagged with its source
    chunk or [opinion]) plus verification against the cited chunk, optionally
    requiring a supporting quote per flag. Planned for the latency/pipeline
    redesign. Switch with config.fact_check.FACT_CHECK_ENFORCE_NORMAL_MODE.
    """
    return bool(state.get("no_specifics")) or cfg.FACT_CHECK_ENFORCE_NORMAL_MODE


def fact_check_node(state: PipelineState) -> PipelineState:
    """Enforce the fact check (no-specifics mode, or normal mode when the flag is on).
    Otherwise mark it pending: run_pipeline hands back log_fact_check to run after
    the response."""
    post = state.get("current_draft", "")
    user_id = state["user_id"]
    if not enforced(state):
        state["fact_check"] = {"mode": "log_only", "flagged": [], "rewrites": [], "outcome": "pending"}
        return state
    record: dict[str, Any] = {"mode": "enforce", "flagged": [], "rewrites": [], "outcome": "skipped"}
    state["fact_check"] = record
    if not post.strip():
        return state

    try:
        flagged = _judge(post, state, user_id, "fact_check")
        record["flagged"] = flagged
        if not flagged:
            record["outcome"] = "all_supported"
            return state

        listed = "\n".join(f"{i + 1}. {c['sentence']} (unsupported: {c['why'] or c['type']})" for i, c in enumerate(flagged))
        message = complete(
            model=SONNET,
            max_tokens=1000,
            messages=[{"role": "user", "content": REWRITE_PROMPT.format(post=post, sentences=listed)}],
            user_id=user_id,
            event_type="fact_check_rewrite",
        )
        rewrites = [str(r).strip() for r in _parse_json_array(message.content[0].text)]

        revised = post
        pairs, unplaced = [], []
        for i, claim in enumerate(flagged):
            new = rewrites[i] if i < len(rewrites) else ""
            replaced = _replace_sentence(revised, claim["sentence"], new) if new else revised
            if replaced != revised:
                revised = replaced
                pairs.append((claim, new))
            else:
                unplaced.append(claim)  # no rewrite returned, or its sentence wasn't found

        recheck = [c["sentence"] for c in _judge(revised, state, user_id, "fact_check_recheck")]
        still_bad = []
        for claim, new in pairs:
            ok = not any(r in new or new in r for r in recheck)
            record["rewrites"].append({
                "sentence": claim["sentence"], "type": claim["type"], "why": claim["why"],
                "rewrite": new, "recheck": "supported" if ok else "unsupported",
                "outcome": "rewritten" if ok else "removed",
            })
            if not ok:
                still_bad.append(Specific(claim["type"], new, new.lower()))
        for claim in unplaced:
            record["rewrites"].append({"sentence": claim["sentence"], "type": claim["type"], "why": claim["why"],
                                       "rewrite": "", "recheck": "", "outcome": "removed"})
            still_bad.append(Specific(claim["type"], claim["sentence"], claim["sentence"].lower()))

        # STOPGAP: removing one sentence
        # can orphan the next ("Not because…"). The fix is citation-based drafting.
        if still_bad:
            revised = remove_sentences(revised, still_bad)
        record["outcome"] = "removed" if still_bad else "rewritten"
        state["current_draft"] = revised
        record_draft(state, "fact_check")
    except Exception as exc:
        logger.warning("fact_check: %s; post left unchanged", exc)
        record["outcome"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    return state


def log_fact_check(state: PipelineState, trace_id: str) -> None:
    """Log-only fact check of the final post: judge once, change nothing, write the
    flags to the trace (node_outputs.fact_check). Runs after /generate has
    responded (FastAPI BackgroundTasks). Never raises."""
    from memory.trace_store import update_trace_fact_check

    user_id = state["user_id"]
    post = state.get("final_post") or state.get("current_draft", "")
    record: dict[str, Any] = {"mode": "log_only", "flagged": [], "rewrites": [], "outcome": "logged"}
    try:
        if post.strip():
            record["flagged"] = _judge(post, state, user_id, "fact_check")
    except Exception as exc:
        logger.warning("fact_check (log-only): %s", exc)
        record["outcome"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
    try:
        update_trace_fact_check(trace_id, user_id, record)
    except Exception:
        logger.exception("fact_check (log-only): trace update failed for %s", trace_id)
