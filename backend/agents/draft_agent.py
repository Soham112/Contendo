import logging

from agents.archetype_agent import choose_archetype
from llm.client import SONNET, complete
from memory.profile_store import profile_voice_context
from pipeline.state import PipelineState
from pipeline.trace import record_draft
from utils.formatters import get_archetype, get_format_instructions, word_count_rule
from utils.frames import NO_CHUNKS_BLOCK, PERSPECTIVES, format_chunks_by_frame, frame_rules
from utils.specifics import find_violations, guard_entry, guard_sources, remove_sentences, retry_note

logger = logging.getLogger(__name__)


def _get_grounding_instruction(confidence: str) -> str:
    """Prompt calibration for retrieval confidence; "" when it is high.

    Says how to write with thin material. Length is not set here: see
    utils.formatters.word_count_rule.
    """
    if confidence == "high":
        return ""

    if confidence == "medium":
        return """
GROUNDING CALIBRATION:
You have moderate knowledge base coverage on this topic.
Use what is available. Do not invent specifics not present in the chunks.
If you lack an example, make the point through reasoning rather than
supplying a named incident, a number or a date.
A tighter post with real grounding beats a longer post with filler.
""".strip()

    return """
GROUNDING CALIBRATION:
The knowledge base has limited content on this specific topic.
Write a focused, honest post based only on what is actually in the chunks.
Rules for this post:
- If you only have one real idea from the chunks, write that one idea
    well and stop. Do not stretch.
- Write from an analytical or observational perspective, not fabricated
    personal experience
- No invented numbers, timestamps, colleague names, or specific incidents
- Do not tell the reader that your knowledge is limited — just write
    what you know
- Stopping with something real is always better than padding with filler
""".strip()


_NO_SPECIFICS_RULE = """NO-SPECIFICS RULE (highest priority — overrides all other instructions, including the knowledge base, profile and writing samples):
The user's notes don't cover this topic, and they asked for an opinion post anyway.
- Write what you think about the topic and why: a view, an argument, a pattern.
- Use no number, percentage, money amount, date, month, day of the week, duration, count, or name of a person, company, product or project, unless it appears in the topic or the additional context above.
- Tell no stories presented as things that happened: no incidents, customers, colleagues, projects or results ("at my last job", "we shipped", "last quarter").
- Frame claims as views: "I think", "the pattern I keep seeing", "most teams"."""


_FIRST_POST_INSTRUCTION = """FIRST POST RULE (overrides visual placeholder rules):
This is the user's very first generated post. Keep it short and punchy — a quick win.
- Do NOT include any [DIAGRAM: ...] or [IMAGE: ...] placeholders. None. Ever. In a first post.
- No multi-section structure. One tight idea, one strong finish.
- The goal is to prove the system works, not to show off every feature."""

_NO_NOTES_RULE = """NO NOTES RULE (highest priority — overrides all other instructions):
No notes relevant to this topic were found. Your only material is the topic and
the additional context above.
Do NOT write any personal stories, specific incidents, named colleagues,
specific numbers (scores, percentages, timeframes), or events presented
as things that happened to this person, unless the topic or context states them.
Write from an observational or analytical perspective:
- "Most teams underestimate feature engineering" not "At my last job we saw..."
- "The pattern is..." not "When we hit 0.71 AUC..."
- "The instinct is usually to change the model. It's rarely the right call."
A post that shares a sharp observation is better than one that invents a story
the author never lived."""

SYSTEM_PROMPT = """You are a ghostwriter. You write a post from the sources below, in the voice of the author described below. The sources decide what the post says. The author profile decides only how it sounds.

Author voice (voice, audience and style only; never a source of content, stories or facts):
{profile_context}

Format and tone instructions:
{format_instructions}
{word_count_rule}

Knowledge base (use what's relevant, ignore the rest):
{retrieved_chunks}

Topic: {topic}
{context_section}
TOPIC RULE: Write about the topic as given. Don't frame it as an analogy or metaphor for the author's professional field, and don't pull in their work, projects or opinions unless the topic or context asks for it.
{posted_topics_section}
{perspective_rule}
{grounding_instruction}
{first_post_instruction}
Write the draft now. Do not add any preamble or explanation; output only the post content itself.

---
POST STRUCTURE: write this post as a {archetype_name}:
{archetype_instructions}
The structure is a shape, not a checklist: leave out any section the sources cannot fill.
---

---
SOURCE RULES (mandatory):
{source_rules}
FABRICATION RULE:
Never invent incidents, dates, names, numbers, results or events. A first-person
event may come only from an OWN EXPERIENCE chunk above, or from what the author
states in the topic or the additional context. The author profile is not a
source of stories: never set an incident at a company, project or role it names.
---

---
VISUAL PLACEHOLDER RULES (mandatory):
For technical posts about systems, pipelines, architectures, or processes: you MUST include at least one [DIAGRAM: detailed description] placeholder.
The description must be specific enough to draw from.
Good: [DIAGRAM: flowchart showing 5 RAG pipeline stages with failure points marked in red at retrieval layer]
Bad: [DIAGRAM: RAG diagram]

For personal or story posts: include one [IMAGE: description] only if a real photo or screenshot would genuinely strengthen the post.

Never force a diagram into opinion pieces or short punchy posts where the words are the point.
---"""

_CROSS_SOURCE_RULE = """CROSS-SOURCE RULE:
Each chunk above is a separate source. Never link facts from different sources as
cause and effect, sequence or result unless one source states that link. Facts
from separate notes stay separate.
Never put an own-experience claim and an external-source claim in the same sentence.
When a paragraph uses both, state the author's own point first, then bring in the
source as support and say where it came from.
"""


def _source_rules(chunks: list[dict], profile: dict) -> str:
    """The per-frame writing rules for the frames present in these chunks."""
    rules = frame_rules(chunks, profile)
    if not rules:
        return ""
    return (
        "Each group of chunks in the knowledge base has a label. Write from each group by its rule.\n\n"
        f"{rules}\n\n{_CROSS_SOURCE_RULE}"
    )


def _format_retrieval_context(state: PipelineState) -> str:
    """The knowledge base block: the bundle's chunks grouped by frame, or the
    flat chunk list when there is no bundle (flat retrieval fallback)."""
    bundle_chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])
    if bundle_chunks:
        return format_chunks_by_frame(bundle_chunks, state.get("profile") or {})
    flat_chunks = state.get("retrieved_chunks", [])
    if flat_chunks:
        return "\n\n---\n\n".join(f"[Chunk {i + 1}]\n{chunk}" for i, chunk in enumerate(flat_chunks))
    return NO_CHUNKS_BLOCK


def _prepend(rule: str, rest: str) -> str:
    return rule + ("\n\n" + rest if rest else "")


def _build_prompt(state: PipelineState, chunks_text: str) -> str:
    profile = state["profile"]
    is_first_post = bool(state.get("first_post"))
    archetype = get_archetype(state.get("archetype", ""))
    bundle_chunks = (state.get("retrieval_bundle") or {}).get("chunks", [])

    context = (state.get("context") or "").strip()
    posted_topics = state.get("posted_topics", [])
    posted_topics_section = ""
    if posted_topics:
        listed = "\n".join(f"- {t}" for t in posted_topics)
        posted_topics_section = (
            f"Topics you have already written about — do not repeat these angles, find a fresh perspective:\n{listed}\n"
        )

    grounding_instruction = _get_grounding_instruction(state.get("retrieval_confidence", "medium"))
    # has_chunks is set by retrieval_node; fall back to what this state holds.
    has_chunks = state.get("has_chunks", bool(bundle_chunks or state.get("retrieved_chunks")))
    if not has_chunks:
        grounding_instruction = _prepend(_NO_NOTES_RULE, grounding_instruction)
    if state.get("no_specifics"):
        grounding_instruction = _prepend(_NO_SPECIFICS_RULE, grounding_instruction)

    return SYSTEM_PROMPT.format(
        profile_context=profile_voice_context(profile),
        format_instructions=get_format_instructions(
            state["format"],
            "concise" if is_first_post else state.get("length", "standard"),
            state["tone"],
        ),
        word_count_rule=word_count_rule(state.get("length_target")),
        retrieved_chunks=chunks_text,
        topic=state["topic"],
        context_section=f"Additional context: {context}" if context else "",
        posted_topics_section=posted_topics_section,
        perspective_rule=PERSPECTIVES.get(state.get("perspective", ""), ""),
        grounding_instruction=grounding_instruction,
        first_post_instruction=_FIRST_POST_INSTRUCTION if is_first_post else "",
        archetype_name=archetype.name,
        archetype_instructions=archetype.structure,
        source_rules=_source_rules(bundle_chunks, profile),
    )


def draft_node(state: PipelineState) -> PipelineState:
    # One Haiku call picks the archetype from the types the sources allow.
    decision = choose_archetype(state)
    state["archetype"] = decision["archetype"]
    state["archetype_decision"] = decision

    chunks_text = _format_retrieval_context(state)
    prompt = _build_prompt(state, chunks_text)
    state["draft_frame_block"] = chunks_text

    def write(violations, event_type: str) -> str:
        message = complete(
            model=SONNET,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt + retry_note(
                violations, no_specifics=bool(state.get("no_specifics")), node="draft")}],
            user_id=state["user_id"],
            event_type=event_type,
            usage_metadata={
                "topic": state.get("topic", ""),
                "format": state.get("format", ""),
                "archetype": state.get("archetype", ""),
            },
        )
        return message.content[0].text.strip()

    # Specifics guard: the draft may use only facts from the chunks, the profile,
    # the topic and the context, and first-person incidents only from
    # self-authored chunks. Retry once; then drop the sentences still at fault.
    sources = guard_sources(state)
    draft = write([], "generate")
    first = find_violations(draft, sources)
    if first:
        draft = write(first, "generate_retry")
        second = find_violations(draft, sources)
        state["specifics_guard"] = [*state.get("specifics_guard", []),
                                    guard_entry("draft", 0, first, second, fallback="sentences_removed")]
        if second:
            logger.warning("draft: retry still had %s; removing those sentences", [v.text for v in second])
            draft = remove_sentences(draft, second)

    state["current_draft"] = draft
    record_draft(state, "draft")

    return state
