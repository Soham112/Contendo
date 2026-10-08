"""Shared state builders for the generation-alignment tests (length, archetype
selection, perspective and frames, structured failures)."""

import pathlib

from tests.conftest import ARCHETYPE_GENERAL

USER = "user-align"
BACKEND = pathlib.Path(__file__).resolve().parents[1]
PROFILE = {
    "name": "Mara", "role": "Data scientist",
    "bio": "Spent nine years at Fernhollow building forecasting systems",
    "topics_of_expertise": ["forecasting"],
    "opinions": ["Dashboards are where insight goes to die"],
    "voice_descriptors": ["dry"],
    "writing_rules": ["Concrete examples over abstract claims"],
    "writing_samples": ["Last quarter we cut churn by 37% at Oakline."],
}
OWN = {"text": "We rebuilt the ranker in March and latency fell.", "memory_context": "work",
       "source_type": "note", "source_title": "Ranker rebuild notes", "tags": "ranking"}
ARTICLE = {"text": "The talk argues that intervals beat point forecasts.", "memory_context": "learning",
           "source_type": "youtube", "source_title": "Forecast intervals talk", "tags": "statistics"}
OBSERVED = {"text": "Teams keep shipping dashboards nobody opens.", "memory_context": "observation",
            "source_type": "note", "source_title": "Dashboard pattern", "tags": "analytics"}
STORY = {"incident_report", "personal_story", "before_after"}

# The founder-06 smoke-eval case: a first-person burnout note stored as an observation
# (so not self-authored) and an investor-update template stored as the author's work.
BURNOUT = {
    "memory_context": "observation", "source_type": "personal_note", "source_title": "The month I burned out",
    "tags": "burnout",
    "text": ("Last spring I burned out without noticing. The tell was not tiredness. It was that I stopped "
             "reading customer emails, which I normally love, and started answering them with one line.\n\n"
             "What helped: telling my co-founder, taking a full week offline, and moving investor updates "
             "from weekly to monthly. What did not help: productivity apps."),
}
INVESTOR_UPDATE = {
    "memory_context": "work", "source_type": "personal_note", "source_title": "Monthly investor update template",
    "tags": "fundraising",
    "text": ("The monthly investor update I send to Harbor Ventures and our angels.\n\n"
             "Rule: the \"what went wrong\" section is never empty. Since Saltmarsh Labs started sending this "
             "format, the number of useful intros from investors went from about one a quarter to three a month."),
}


def make_state(chunks=(), **overrides):
    from utils.formatters import resolve_length_target
    from utils.frames import decide_perspective

    chunks = list(chunks)
    state = {
        "user_id": USER, "quality": "standard", "profile": PROFILE,
        "topic": "Forecast intervals", "context": "", "format": "linkedin post", "tone": "casual",
        "length": "standard", "retrieval_bundle": {"chunks": chunks}, "retrieved_chunks": [],
        "has_chunks": bool(chunks), "retrieval_confidence": "high", "posted_topics": ["Earlier"],
        "first_post": False, "critic_brief": {}, "current_draft": "A draft.", "iterations": 0,
        "draft_history": [], "perspective": decide_perspective(chunks, PROFILE),
        "length_target": resolve_length_target("linkedin post", "standard"),
    }
    state.update(overrides)
    return state


def last_prompt(claude, call=-1) -> str:
    return claude.calls[call]["messages"][-1]["content"]


def draft_prompt(claude, state, archetype=ARCHETYPE_GENERAL) -> str:
    """Run draft_node on state and return the prompt the draft call received."""
    from agents.draft_agent import draft_node

    claude.queue(archetype, "The draft.")
    draft_node(state)
    return last_prompt(claude)


def agent_sources() -> dict[str, str]:
    """Source text of every agent module plus the formatters and frames modules."""
    return {p.name: p.read_text() for p in (BACKEND / "agents").glob("*.py")} | {
        "formatters.py": (BACKEND / "utils" / "formatters.py").read_text(),
        "frames.py": (BACKEND / "utils" / "frames.py").read_text(),
    }
