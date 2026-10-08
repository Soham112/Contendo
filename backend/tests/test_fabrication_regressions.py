"""Regression tests for two real fabrications (generation traces 28636114 and
25321609, 2026-10-03).

1. Hiking opinion post ("My favourite hiking trails in the Lake District",
   no_specifics=True, no chunks): the drafter's post was clean, but the critic
   suggested "At Data Axle, I watched a model tank in production..." and the
   humanizer pasted it in. The guard let it through: it only checked numbers.
2. "AI agents vs AI assistants" (5 IBM article chunks, no self-authored
   chunks): the critic asked for "a concrete failure example from your own
   agentic AI work" and "a real debugging moment ('I learned this the hard way
   at 2am')"; the humanizer turned the article's "agents get stuck in infinite
   feedback loops" into "I've watched agents hit planning loops... At 2am".

Texts below are copied from those traces.
"""

import json

import pytest

from agents.humanizer_agent import strip_quoted
from utils.frames import authorship, chunk_frame

USER = "user-regression"

PROFILE = {
    "name": "Soham Patil",
    "role": "Data Scientist, ML Engineer & International Badminton Player",
    "bio": (
        "3+ years building production ML systems — from regression models on 10M+ business records "
        "to LLM pipelines and agentic AI. Started as a fresher at Data Axle, got promoted in 1.5 years, "
        "mentored 5 people, and pulled outsourced work back in-house."
    ),
    "writing_rules": [
        "Concrete examples over abstract claims — use real numbers, real situations.",
        "Reference real moments — a mistake, something surprising, a specific number.",
        "Short paragraphs — max 3 sentences.",
    ],
    "topics_of_expertise": ["Production ML and MLOps", "RAG systems and LLM pipelines", "Agentic AI workflows"],
    "opinions": [
        "Production and notebook are two completely different worlds. "
        "Nobody tells you how different until you're debugging at 2am."
    ],
    "words_to_avoid": ["leverage", "delve"],
}

# --- Case 1: hiking opinion post ---------------------------------------------------

HIKING_TOPIC = "My favourite hiking trails in the Lake District"
HIKING_DRAFT = (
    "The Lake District doesn't care how fit you think you are.\n\n"
    "Most people treat mountain hikes like a plan you execute. The weather windows are short, "
    "the ground shifts from firm to boggy fast, and visibility drops with almost no warning.\n\n"
    "The best trails teach you something about how you operate under uncertainty."
)
HIKING_CRITIC_BRIEF = {
    "hook": {"verdict": "strong", "fix": None},
    "substance": {
        "verdict": "needs_work",
        "fix": (
            "Replace the hiking analogy with a real technical moment from your production ML or badminton "
            "experience. Use a specific number, a named project, or a concrete failure (e.g., 'At Data Axle, "
            "I watched a model tank in production because we didn't monitor data drift — same as hiking blind "
            "into cloud cover'). Analogies weaken when they're the entire post instead of the frame around a "
            "real example."
        ),
    },
    "structure": {"verdict": "strong", "fix": None},
    "voice": {
        "verdict": "needs_work",
        "fix": (
            "The post is too removed from Soham's voice. Ground it: 'I learned this the hard way hiking the "
            "Lake District last month, and immediately saw it in how we debug models at 2am' or connect it "
            "directly to a named project or badminton moment."
        ),
    },
    "overall": "needs_revision",
}
HIKING_HUMANIZED = (
    "At Data Axle, I watched a model tank in production because we stopped checking inputs after "
    "deployment. The distribution shifted. Nobody caught it until the business did.\n\n"
    "Hiking the Lake District taught me the same lesson from a different direction.\n\n"
    "The model didn't fail because the science was bad. It failed because we stopped paying attention."
)

# --- Case 2: AI agents post ------------------------------------------------------

AGENTS_TOPIC = "AI agents vs AI assistants"
IBM_TAGS = ("ai agents,ai assistants,agentic ai,autonomous systems,large language models,"
            "multi-agent systems,natural language processing")
IBM_CHUNK = {
    "id": "5eab5f63-3f5c-4fab-925f-b3237962968f_5",
    "source_id": "5eab5f63-3f5c-4fab-925f-b3237962968f",
    "source_title": "AI Agents vs. AI Assistants | IBM",
    "source_type": "article",
    "memory_context": None,
    "tags": IBM_TAGS,
    "similarity": 0.6165,
    "text": (
        "Without comprehensive plans or fail at reflecting on their findings, AI agents get stuck in "
        "infinite feedback loops. And because AI agents consider external environments and tools, they "
        "must deal with the changes to those tools. Over time, those changes might cause the agent set up "
        "to break."
    ),
}
AGENTS_DRAFT = (
    "Most people think the hard part of agentic AI is the LLM. It's not. It's the boundary.\n\n"
    "An AI assistant is essentially a very smart function call.\n\n"
    "Infinite feedback loops are a documented failure mode. Tool APIs change. The agent's plan breaks "
    "mid-execution and it just keeps planning."
)
AGENTS_CRITIC_BRIEF = {
    "hook": {"verdict": "strong", "fix": None},
    "substance": {
        "verdict": "needs_work",
        "fix": (
            "Replace the badminton rally analogy with a concrete failure example from your own agentic AI "
            "work — a specific agent you built or debugged that hit an infinite loop, what the symptom was, "
            "and what the termination condition should have been."
        ),
    },
    "structure": {"verdict": "strong", "fix": None},
    "voice": {
        "verdict": "needs_work",
        "fix": (
            "The phrase 'you don't have a system — you have a loop with a credit card attached' is sharp but "
            "feels like a one-liner borrowed from Twitter culture. Tighten it to match Soham's direct, grounded "
            "style: replace with something like 'you don't have a system — you have a cost sink' or anchor it "
            "to a real debugging moment ('I learned this the hard way at 2am')."
        ),
    },
    "overall": "needs_work",
}
AGENTS_HUMANIZED = (
    "Most people think the hard part of agentic AI is the LLM. It's not. It's knowing when to stop.\n\n"
    "Here's what I learned the hard way.\n\n"
    "I've watched agents hit planning loops mid-execution because a tool API changed and nobody defined "
    "what failure looked like. The agent didn't crash. It just kept re-planning. At 2am, debugging that, "
    "you realize fast: the LLM was never the problem."
)


def _state(**overrides):
    state = {
        "quality": "standard",
        "user_id": USER,
        "topic": "",
        "context": "",
        "format": "thread",  # no word-count rule in the prompts
        "length": "standard",
        "tone": "technical",
        "profile": PROFILE,
        "retrieval_bundle": {"chunks": []},
        "retrieved_chunks": [],
        "critic_brief": {},
        "current_draft": "",
        "iterations": 0,
        "draft_history": [],
        "specifics_guard": [],
        "no_specifics": False,
    }
    state.update(overrides)
    return state


def _hiking_state(**overrides):
    return _state(**{"topic": HIKING_TOPIC, "no_specifics": True, "current_draft": HIKING_DRAFT,
                     "critic_brief": HIKING_CRITIC_BRIEF, **overrides})


def _agents_state(**overrides):
    return _state(**{"topic": AGENTS_TOPIC, "current_draft": AGENTS_DRAFT, "critic_brief": AGENTS_CRITIC_BRIEF,
                     "retrieval_bundle": {"chunks": [IBM_CHUNK]},
                     "retrieved_chunks": [f"[source_type: article] {IBM_CHUNK['text']}"], **overrides})


def _prompt(call):
    return call["messages"][-1]["content"]


def _kinds(violations):
    return {(v.kind, v.text[:40]) for v in violations}


# --- Critic: diagnoses only, knows the mode and the authorship --------------------

def test_hiking_critic_prompt_states_no_specifics_and_no_self_chunks(claude):
    from agents.critic_agent import critic_node

    claude.queue('{"hook": {"verdict": "strong", "fix": null}, "substance": {"verdict": "strong", "fix": null}, '
                 '"structure": {"verdict": "strong", "fix": null}, "voice": {"verdict": "strong", "fix": null}, '
                 '"overall": "postable"}')
    critic_node(_hiking_state(archetype="teach_me_something"))
    prompt = _prompt(claude.calls[0])
    assert "MODE: opinion post without specifics" in prompt
    assert "None of the chunks are self-authored. Never ask for personal experience" in prompt
    assert "Never write example sentences, replacement text, or anything in quotation marks" in prompt
    assert "real numbers from the knowledge base" not in prompt  # old SUBSTANCE wording


def test_agents_critic_prompt_labels_the_article_as_external(claude):
    from agents.critic_agent import critic_node

    claude.queue('{"overall": "postable"}')
    critic_node(_agents_state(archetype="teach_me_something"))
    prompt = _prompt(claude.calls[0])
    assert "[frame: EXPERT_OUTSIDER | authorship: external | source: article]" in prompt
    assert "None of the chunks are self-authored" in prompt
    assert "MODE: opinion post without specifics" not in prompt


def test_critic_allows_experience_only_from_self_chunks(claude):
    from agents.critic_agent import critic_node

    claude.queue('{"overall": "postable"}')
    own = {**IBM_CHUNK, "memory_context": "work"}
    critic_node(_agents_state(archetype="teach_me_something", retrieval_bundle={"chunks": [own]}))
    prompt = _prompt(claude.calls[0])
    assert "authorship: self" in prompt
    assert "Ask for first-person experience only where a self-authored chunk describes it" in prompt


def test_writing_rules_that_push_for_numbers_are_qualified():
    from memory.profile_store import profile_to_context_string

    rendered = profile_to_context_string(PROFILE)
    qualifier = "(Only numbers and situations stated in the knowledge base, the profile or the request."
    assert rendered.count(qualifier) == 2  # "real numbers, real situations" and "a specific number"
    assert "Short paragraphs — max 3 sentences.\n" in rendered + "\n"


# --- Humanizer: facts first, quotes stripped, fabrications reverted ----------------

def test_critic_quotes_are_stripped_before_the_humanizer():
    hiking = strip_quoted(HIKING_CRITIC_BRIEF["substance"]["fix"])
    assert "Data Axle" not in hiking and "e.g." not in hiking
    voice = strip_quoted(HIKING_CRITIC_BRIEF["voice"]["fix"])
    assert "last month" not in voice and "2am" not in voice
    agents = strip_quoted(AGENTS_CRITIC_BRIEF["voice"]["fix"])
    assert "2am" not in agents and "cost sink" not in agents and "credit card" not in agents
    assert "Soham's direct, grounded style" in agents  # apostrophes are not quotes


def test_hiking_humanizer_never_sees_the_critics_suggestion(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue(HIKING_DRAFT)
    humanizer_node(_hiking_state())
    prompt = _prompt(claude.calls[0])
    assert prompt.index("Facts are fixed.") < prompt.index("CRITIC BRIEF")
    assert "The critic brief below describes problems, not content." in prompt
    critic_section = prompt[prompt.index("CRITIC BRIEF"):prompt.index("AI writing patterns")]
    assert "Data Axle" not in critic_section and "2am" not in critic_section and "last month" not in critic_section


def test_agents_humanizer_never_sees_the_2am_suggestion(claude):
    from agents.humanizer_agent import humanizer_node

    claude.queue(AGENTS_DRAFT)
    humanizer_node(_agents_state())
    critic_section = _prompt(claude.calls[0]).split("CRITIC BRIEF", 1)[1].split("AI writing patterns", 1)[0]
    assert "2am" not in critic_section and "credit card" not in critic_section


# --- Drafter: guarded too -------------------------------------------------------

def _draft_state(**overrides):
    return _agents_state(current_draft="", critic_brief={}, retrieval_confidence="high",
                         retrieved_chunk_count=1, posted_topics=["Something else"], first_post=False,
                         **overrides)


def test_draft_node_retries_an_invented_number(claude):
    from agents.draft_agent import draft_node

    invented = "Agents loop in 40% of runs. Infinite feedback loops are a documented failure mode."
    clean = "Infinite feedback loops are a documented failure mode. Define the exit before the agent."
    claude.queue("teach_me_something", invented, clean)
    state = draft_node(_draft_state())

    assert "Write the post again without them" in _prompt(claude.calls[2])
    assert "- 40%" in _prompt(claude.calls[2])
    assert state["current_draft"] == clean
    assert state["specifics_guard"][0]["node"] == "draft"
    assert state["draft_frame_block"].startswith("EXPERT OUTSIDER PERSPECTIVE")


def test_draft_node_removes_the_sentence_when_the_retry_still_invents(claude):
    from agents.draft_agent import draft_node

    invented = ("Infinite feedback loops are a documented failure mode. "
                "Agents loop in 40% of runs. Define the exit first.")
    claude.queue("teach_me_something", invented, invented)
    state = draft_node(_draft_state())

    assert state["current_draft"] == "Infinite feedback loops are a documented failure mode. Define the exit first."
    assert state["specifics_guard"][0]["outcome"] == "sentences_removed"


# --- Trace: what the drafter saw, and why ------------------------------------------

def test_trace_records_frames_mode_frame_block_and_critic_brief():
    from pipeline.trace import build_trace_row

    state = _hiking_state(retrieval_bundle={"chunks": [IBM_CHUNK]}, draft_frame_block="EXPERT OUTSIDER ...")
    row = build_trace_row(state, [])
    [chunk] = row["retrieved"]
    assert chunk["frame"] == "EXPERT_OUTSIDER" and chunk["authorship"] == "external"
    assert chunk["memory_context"] is None and chunk["tags"] == IBM_TAGS
    assert row["node_outputs"]["no_specifics"] is True
    assert row["node_outputs"]["draft_frame_block"] == "EXPERT OUTSIDER ..."
    assert row["node_outputs"]["critic_brief"] == HIKING_CRITIC_BRIEF


# --- Legacy authorship: memory_context NULL --------------------------------------


@pytest.mark.parametrize("source_type, memory_context, expected", [
    ("note", None, "self"),               # typed notes and Obsidian imports
    ("personal_note", None, "self"),
    ("note", "learning", "external"),     # an explicit memory_context always wins
    ("note", "work", "self"),
    ("article", None, "external"),        # URLs, scraped pages and file uploads
    ("youtube", None, "external"),
    ("image", None, "external"),
    ("saved_content", None, "external"),
    ("article", "work", "self"),
])
def test_legacy_chunks_are_self_authored_only_when_the_user_wrote_them(source_type, memory_context, expected):
    chunk = {"text": "x", "source_type": source_type, "memory_context": memory_context, "tags": "agentic ai"}
    assert authorship(chunk_frame(chunk, PROFILE)) == expected


# --- Critic: topic adherence ---------------------------------------------------

def test_critic_checks_the_topic_first_and_never_steers_to_the_profile(claude):
    from agents.critic_agent import critic_node

    claude.queue('{"overall": "postable"}')
    critic_node(_hiking_state(archetype="teach_me_something", context="Keep it about the walks"))
    prompt = _prompt(claude.calls[0])
    assert f"Topic as given: {HIKING_TOPIC}" in prompt
    assert "Additional context: Keep it about the walks" in prompt
    assert prompt.index("1. TOPIC") < prompt.index("2. HOOK")
    assert "Never suggest connecting the post to the author's opinions, expertise, projects or work" in prompt
    assert '{"topic": {"verdict"' in prompt


def test_humanizer_fixes_topic_drift_first():
    from agents.humanizer_agent import _format_critic_brief

    section, instruction = _format_critic_brief({
        "hook": {"verdict": "needs_work", "fix": "The hook is generic."},
        "topic": {"verdict": "needs_work", "fix": "The post drifts into retrieval engineering; return to the trails."},
    })
    assert section.index("- TOPIC:") < section.index("- HOOK:")
    assert "in this order: topic, hook, substance, structure, voice" in instruction


def test_drafter_prompt_keeps_the_post_on_the_topic_as_given(claude):
    # Hiking replay: the drafter framed the trails as "a retrieval problem" for an ML engineer.
    from agents.draft_agent import draft_node

    claude.queue("teach_me_something", "The Lake District rewards the honest route, not the ambitious one.")
    draft_node(_draft_state(topic=HIKING_TOPIC, no_specifics=True, retrieval_bundle={"chunks": []},
                            retrieved_chunks=[]))
    prompt = _prompt(claude.calls[1])
    rule = ("TOPIC RULE: Write about the topic as given. Don't frame it as an analogy or metaphor for the "
            "author's professional field")
    assert rule in prompt
    assert prompt.index(f"Topic: {HIKING_TOPIC}") < prompt.index(rule)


# --- Final fact check ------------------------------------------------------------
#
# The fake Claude returns the verdicts, so these tests check what the fact
# checker is allowed to see (sources per mode) and what it does with a verdict.
# Real Haiku verdicts on the same four cases were checked in a scratch run.

LEGS = "My legs gave out on a Lake District trail that looked easy on paper."
DATA_AXLE = "I watched a model tank at Data Axle."
RESEARCH = "Research shows agents loop when tools change."
SELF_NOTE = {
    "text": "Debugged our support agent last spring: it kept re-planning after the ticketing API changed, "
            "because we never defined what failure looked like.",
    "source_type": "note", "memory_context": "work",
}
PARAPHRASE = "Our support agent kept re-planning after an API change, because we never defined failure."


def _flags(post, *items):
    """Judge response listing (sentence, type, why) as unsupported, by sentence number."""
    from agents.fact_check_agent import _split_sentences

    sentences = _split_sentences(post)
    return json.dumps([{"i": sentences.index(sent) + 1, "type": t, "why": why} for sent, t, why in items])


def _fc_state(post, **overrides):
    return _state(**{"current_draft": post, "topic": AGENTS_TOPIC, **overrides})


@pytest.fixture
def enforce_normal(monkeypatch):
    """Turn on normal-mode enforcement (off by default: log-only stopgap)."""
    from config import fact_check as cfg

    monkeypatch.setattr(cfg, "FACT_CHECK_ENFORCE_NORMAL_MODE", True)


def test_fact_check_rewrites_an_invented_event_in_no_specifics_mode(claude):
    from agents.fact_check_agent import fact_check_node

    post = f"{LEGS}\n\nGradient matters more than total ascent."
    rewrite = "A trail that looks easy on paper can still wear your legs down."
    claude.queue(_flags(post, (LEGS, "event", "no source describes this")), json.dumps([rewrite]), "[]")
    state = fact_check_node(_hiking_state(current_draft=post))

    judge = _prompt(claude.calls[0])
    assert f"1. {LEGS}\n2. Gradient matters more than total ascent." in judge
    assert "only the request can support an event, never the notes or the identity" in judge
    assert "- name: in this mode, any named place, person, organisation, product or trail" in judge
    assert "SELF-AUTHORED NOTES (the author's own experiences; the only notes that can support a first-person event):\nnone" in judge
    assert "AUTHOR IDENTITY (supports only who the author is, never what happened to them):\nnone (not allowed in this mode)" in judge
    assert [c["model"] for c in claude.calls] == ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
    assert state["current_draft"] == f"{rewrite}\n\nGradient matters more than total ascent."
    record = state["fact_check"]
    assert record["outcome"] == "rewritten"
    assert record["flagged"] == [{"i": 1, "sentence": LEGS, "type": "event", "why": "no source describes this"}]
    assert record["rewrites"] == [{"sentence": LEGS, "type": "event", "why": "no source describes this",
                                   "rewrite": rewrite, "recheck": "supported", "outcome": "rewritten"}]
    assert state["draft_history"][-1]["node"] == "fact_check"


def test_fact_check_rewrites_trail_names_in_no_specifics_mode(claude):
    from agents.fact_check_agent import fact_check_node

    named = "The trails I keep returning to are Helvellyn via Striding Edge and the Langdale Pikes circuit."
    rewrite = "The trails worth returning to are the ones that stay honest in the middle section."
    claude.queue(_flags(named, (named, "name", "trail names not in topic")), json.dumps([rewrite]), "[]")
    state = fact_check_node(_hiking_state(current_draft=named))
    assert state["current_draft"] == rewrite
    assert state["fact_check"]["flagged"][0]["type"] == "name"


def test_fact_check_removes_the_data_axle_event_when_the_rewrite_is_still_unsupported(claude, enforce_normal):
    from agents.fact_check_agent import fact_check_node

    post = f"{DATA_AXLE} Monitor inputs, not just outputs."
    rewrite = "At Data Axle, models tanked when nobody watched the inputs."
    revised = f"{rewrite} Monitor inputs, not just outputs."
    claude.queue(
        _flags(post, (DATA_AXLE, "event", "no self-authored note")),
        json.dumps([rewrite]),
        _flags(revised, (rewrite, "event", "still an unsupported event")),
    )
    state = fact_check_node(_fc_state(post, retrieval_bundle={"chunks": [IBM_CHUNK]}))

    judge = _prompt(claude.calls[0])
    # Normal mode: identity is name and role (no employer without work experience
    # nodes); the article is an other source, never support for an event; no name rule.
    assert "Name: Soham Patil\nRole: Data Scientist" in judge and "Employers:" not in judge
    assert IBM_CHUNK["text"] in judge.split("OTHER SOURCES", 1)[1].split("THE REQUEST", 1)[0]
    assert "- name: in this mode" not in judge
    assert len(claude.calls) == 3
    assert state["current_draft"] == "Monitor inputs, not just outputs."
    assert state["fact_check"]["outcome"] == "removed"
    assert state["fact_check"]["rewrites"][0]["recheck"] == "unsupported"


def test_fact_check_accepts_a_paraphrase_of_a_self_authored_note(claude, enforce_normal):
    from agents.fact_check_agent import fact_check_node

    claude.queue("[]")
    state = fact_check_node(_fc_state(PARAPHRASE, retrieval_bundle={"chunks": [SELF_NOTE]}))

    judge = _prompt(claude.calls[0])
    assert SELF_NOTE["text"] in judge.split("SELF-AUTHORED NOTES", 1)[1].split("OTHER SOURCES", 1)[0]
    assert len(claude.calls) == 1
    assert state["current_draft"] == PARAPHRASE
    assert state["fact_check"] == {"mode": "enforce", "flagged": [], "rewrites": [], "outcome": "all_supported"}


def test_fact_check_accepts_a_research_claim_backed_by_an_external_chunk(claude, enforce_normal):
    from agents.fact_check_agent import fact_check_node

    claude.queue("[]")
    state = fact_check_node(_fc_state(RESEARCH, retrieval_bundle={"chunks": [IBM_CHUNK]}))
    assert len(claude.calls) == 1
    assert state["current_draft"] == RESEARCH


def test_fact_check_ignores_out_of_range_sentence_numbers(claude, enforce_normal):
    from agents.fact_check_agent import fact_check_node

    claude.queue('[{"i": 7, "type": "event", "why": "x"}, {"i": "two", "type": "event", "why": "y"}]')
    state = fact_check_node(_fc_state(RESEARCH))
    assert state["fact_check"]["outcome"] == "all_supported" and len(claude.calls) == 1


def test_fact_check_identity_lists_employers_from_work_experience_in_normal_mode_only(claude, enforce_normal):
    from agents.fact_check_agent import fact_check_node

    nodes = [{"node_type": "work", "entity_name": "Data Axle"}, {"node_type": "education", "entity_name": "UTD"}]
    claude.queue("[]", "[]")
    fact_check_node(_fc_state("I work at Data Axle.", experience_nodes=nodes))
    fact_check_node(_hiking_state(current_draft="I work at Data Axle.", experience_nodes=nodes))
    assert "Employers: Data Axle" in _prompt(claude.calls[0]) and "UTD" not in _prompt(claude.calls[0])
    assert "Employers:" not in _prompt(claude.calls[1])


def test_fact_check_error_leaves_the_post_unchanged(claude, enforce_normal):
    from agents.fact_check_agent import fact_check_node

    claude.queue("not json at all")
    state = fact_check_node(_fc_state(DATA_AXLE))
    assert state["current_draft"] == DATA_AXLE
    assert state["fact_check"]["outcome"] == "error"


def test_fact_check_runs_in_draft_quality_too(claude, enforce_normal):
    from agents.fact_check_agent import fact_check_node

    claude.queue("[]")
    state = fact_check_node(_fc_state("Define the exit first.", quality="draft"))
    assert len(claude.calls) == 1 and state["fact_check"]["outcome"] == "all_supported"


def test_trace_records_the_fact_check():
    from pipeline.trace import build_trace_row

    record = {"flagged": [], "rewrites": [], "outcome": "all_supported"}
    row = build_trace_row(_state(fact_check=record), [])
    assert row["node_outputs"]["fact_check"] == record


def test_normal_mode_node_makes_no_call_and_leaves_the_post_alone(claude):
    from agents.fact_check_agent import fact_check_node

    state = fact_check_node(_fc_state(DATA_AXLE, retrieval_bundle={"chunks": [IBM_CHUNK]}))
    assert claude.calls == []
    assert state["current_draft"] == DATA_AXLE
    assert state["fact_check"]["mode"] == "log_only" and state["fact_check"]["outcome"] == "pending"
