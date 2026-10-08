"""Generation trace: what one pipeline run retrieved, wrote, and called.

Nodes call record_draft() after rewriting current_draft; run_pipeline turns the
final state into a generation_traces row with build_trace_row().
"""

from typing import Any

from pipeline.state import PipelineState
from utils.frames import authorship, chunk_field, chunk_frame


def record_draft(state: PipelineState, node: str) -> None:
    """Append the current draft to draft_history, tagged with node and iteration."""
    state["draft_history"] = [
        *state.get("draft_history", []),
        {
            "node": node,
            "iteration": state.get("iterations", 0),
            "text": state.get("current_draft", ""),
        },
    ]


def _chunk_snapshot(chunk: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Keep ids, scores, attribution and text: chunk ids can dangle after a library delete."""
    frame = chunk_frame(chunk, profile)
    return {
        "chunk_id": chunk.get("id") or chunk.get("chunk_id") or None,
        "source_id": chunk.get("source_id", ""),
        "source_title": chunk.get("source_title", ""),
        "source_type": chunk.get("source_type", ""),
        "similarity": chunk.get("similarity"),
        "bm25_score": chunk.get("bm25_score"),
        "bm25_norm": chunk.get("bm25_norm"),
        "rrf_score": chunk.get("rrf_score"),
        "rrf_rank": chunk.get("rrf_rank"),
        "entity_linked": bool(chunk.get("entity_linked", False)),
        "memory_context": chunk.get("memory_context") or (chunk.get("metadata") or {}).get("memory_context"),
        "tags": chunk_field(chunk, "tags"),
        "frame": frame,
        "authorship": authorship(frame),
        "text": chunk.get("text", ""),
    }


def build_trace_row(state: PipelineState, llm_calls: list[dict]) -> dict[str, Any]:
    """One generation_traces row from the pipeline's final state."""
    chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])
    profile = state.get("profile") or {}
    return {
        "user_id": state["user_id"],
        "topic": state.get("topic", ""),
        "context": state.get("context", ""),
        "format": state.get("format", ""),
        "tone": state.get("tone", ""),
        "length": state.get("length", ""),
        "quality": state.get("quality", ""),
        "retrieval_query": state.get("retrieval_query", ""),
        "retrieval_path": state.get("retrieval_path", ""),
        "retrieval_confidence": state.get("retrieval_confidence", ""),
        "retrieved": [_chunk_snapshot(c, profile) for c in chunks],
        "retrieved_context": state.get("retrieved_context", ""),
        "profile_snapshot": state.get("profile", {}),
        "node_outputs": {
            "no_specifics": bool(state.get("no_specifics")),
            "length_target": state.get("length_target"),
            "perspective": state.get("perspective", ""),
            "archetype_decision": state.get("archetype_decision", {}),
            "draft_frame_block": state.get("draft_frame_block", ""),
            "draft_history": state.get("draft_history", []),
            "critic_brief": state.get("critic_brief", {}),
            "score_history": state.get("score_history", []),
            "specifics_guard": state.get("specifics_guard", []),
            "coverage_gate": state.get("coverage_gate", {}),
            "fact_check": state.get("fact_check", {}),
            "final_post": state.get("final_post", state.get("current_draft", "")),
        },
        "llm_calls": llm_calls,
        "score": state.get("score", 0),
        "iterations": state.get("iterations", 0),
        "archetype": state.get("archetype", ""),
    }
