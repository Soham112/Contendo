from langgraph.graph import StateGraph, END

from pipeline.state import PipelineState
from memory.profile_store import load_profile
from memory.feedback_store import get_all_topics_posted
from agents.retrieval_agent import retrieval_node
from agents.draft_agent import draft_node
from agents.humanizer_agent import humanizer_node
from agents.scorer_agent import scorer_node

SCORE_THRESHOLD = 75
MAX_ITERATIONS = 3


def load_profile_node(state: PipelineState) -> PipelineState:
    state["profile"] = load_profile()
    state["iterations"] = 0
    state["archetype"] = state.get("archetype", "")
    state["posted_topics"] = get_all_topics_posted()
    return state


def finalize_node(state: PipelineState) -> PipelineState:
    state["final_post"] = state["current_draft"]
    return state


def should_retry(state: PipelineState) -> str:
    quality = state.get("quality", "standard")

    if quality in ("draft", "standard"):
        return "finalize"

    # quality == "polished": retry loop up to MAX_ITERATIONS
    if state.get("score", 0) < SCORE_THRESHOLD and state.get("iterations", 0) < MAX_ITERATIONS:
        return "humanizer"
    return "finalize"


def build_graph() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("load_profile", load_profile_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("draft", draft_node)
    graph.add_node("humanizer", humanizer_node)
    graph.add_node("scorer", scorer_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("load_profile")
    graph.add_edge("load_profile", "retrieval")
    graph.add_edge("retrieval", "draft")
    graph.add_edge("draft", "humanizer")
    graph.add_edge("humanizer", "scorer")
    graph.add_conditional_edges(
        "scorer",
        should_retry,
        {
            "humanizer": "humanizer",
            "finalize": "finalize",
        },
    )
    graph.add_edge("finalize", END)

    return graph.compile()


# Singleton compiled graph — imported by main.py
pipeline = build_graph()


def run_pipeline(topic: str, format: str, tone: str, context: str = "", quality: str = "standard", user_id: str = "default") -> dict:
    initial_state: PipelineState = {
        "topic": topic,
        "format": format,
        "tone": tone,
        "context": context,
        "quality": quality,
        "user_id": user_id,
        "iterations": 0,
        "archetype": "",
    }

    result = pipeline.invoke(initial_state)

    return {
        "post": result.get("final_post", result.get("current_draft", "")),
        "score": result.get("score", 0),
        "score_feedback": result.get("score_feedback", []),
        "iterations": result.get("iterations", 1),
        "archetype": result.get("archetype", ""),
    }
