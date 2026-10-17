"""Cited selection rewrite: the stored drafter, passage checks, and one retry.

Source tracking and the historical writer live in refine_agent.py. This module
owns the single-writer model call and its recorded retry/revert outcomes.
"""

import logging
from typing import Any

from agents.refine_agent import (
    EMPTY_REFINE_MESSAGE, REFUSED_MESSAGE, REVERTED_MESSAGE, TRUNCATED_MESSAGE,
    RefineSources, _REFINE_MAX_TOKENS, _split_note,
)
from agents.refine_prompt import build_refine_cited_prompt
from llm.client import REFUSAL, complete, message_text, output_budget
from llm.models import draft_effort
from memory.profile_store import profile_voice_context
from memory.trace_store import append_trace_refine
from pipeline.checks import run_passage_checks
from pipeline.finalise import finalise_marked
from pipeline.redraft import issue_entries

logger = logging.getLogger(__name__)


def refine_cited(selected_text: str, instruction: str, full_post: str, profile: dict[str, Any],
                  sources: RefineSources, user_id: str) -> dict[str, Any]:
    """The single-writer rewrite: the post's own drafter, the stored sources
    block, a marker on every sentence, and the deterministic checks on the
    passage. One retry with the checks' findings; then the selection is kept.

    A reply the model declined, or one cut off at its output limit, is never
    used: the selection is returned unchanged with a message that says which.
    Every outcome is recorded on the trace (node_outputs.refine_selection)."""
    cited = sources.cited
    request = [cited.topic, cited.context, instruction]
    effort = draft_effort(cited.model)
    result = {"rewritten_text": selected_text, "status": "ok", "message": "", "note": "",
              "sources_used": sources.origin, "sources_message": ""}
    attempts: list[dict[str, Any]] = []

    def attempt(event_type: str, previous: str = "", problems: list[dict] | None = None) -> dict[str, Any]:
        prompt = build_refine_cited_prompt(
            profile_context=profile_voice_context(profile, include_identity=not bool((cited.business or {}).get("facts"))), words_to_avoid=profile.get("words_to_avoid", []),
            sources_block=cited.block, topic=cited.topic, context=cited.context, full_post=full_post,
            selected_text=selected_text, instruction=instruction, previous=previous, problems=problems,
            business=cited.business,
            empty_retry=event_type == "refine_selection_retry" and not previous.strip())
        message = complete(
            model=cited.model,
            max_tokens=output_budget(cited.model, _REFINE_MAX_TOKENS),
            messages=[{"role": "user", "content": prompt}],
            user_id=user_id,
            event_type=event_type,
            **({} if effort is None else {"output_config": {"effort": effort}}),
        )
        marked, note = _split_note(message_text(message))
        finalised, stripped = finalise_marked(marked, None)
        spans = [span.as_dict() for span in stripped.spans]
        failures = [{"kind": f.kind, "text": f.text, "start": f.start, "end": f.end} for f in stripped.failures]
        checks = run_passage_checks(finalised.text, spans, failures, cited.source_index, cited.chunks, request, profile, (cited.business or {}).get("facts", ""))
        entry = {"event_type": event_type, "stop_reason": message.stop_reason, "marked": marked, "text": finalised.text,
                 "note": note, "citations": spans, "checks": checks,
                 "reason": "empty_output" if not finalised.text.strip() and not note else None}
        attempts.append(entry)
        return entry

    def finish(**changes: Any) -> dict[str, Any]:
        """The response, with what happened recorded on the trace. Recording never fails the request."""
        answer = {**result, **changes}
        try:
            append_trace_refine(sources.trace_id, user_id, {
                "selected_text": selected_text, "instruction": instruction, "model": cited.model,
                "status": answer["status"], "attempts": attempts})
        except Exception as exc:
            logger.error("refine_selection: trace recording failed category=%s", type(exc).__name__)
        return answer

    def unusable(entry: dict[str, Any]) -> str | None:
        return {REFUSAL: REFUSED_MESSAGE, "max_tokens": TRUNCATED_MESSAGE}.get(entry["stop_reason"])

    first = attempt("refine_selection")
    if unusable(first):
        return finish(status="reverted", message=unusable(first))
    last = first
    if first["checks"]["issues"] or first["reason"] == "empty_output":
        logger.info("refine_selection: first attempt failed checks %s; retrying", first["checks"]["counts"])
        last = attempt("refine_selection_retry", previous=first["marked"],
                       problems=issue_entries(first["checks"]["issues"]))
        if unusable(last):
            return finish(status="reverted", message=unusable(last))
        if last["reason"] == "empty_output":
            return finish(status="reverted", message=EMPTY_REFINE_MESSAGE)
        if last["checks"]["issues"]:
            logger.warning("refine_selection: retry still failed checks %s; keeping the selection", last["checks"]["counts"])
            return finish(status="reverted", message=REVERTED_MESSAGE)
    # A reply that is only a note leaves the selection as it was.
    return finish(rewritten_text=last["text"] or selected_text, note=last["note"])
