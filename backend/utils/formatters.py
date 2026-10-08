"""Prompt building blocks that depend only on the request: length, format, tone
and post archetype. One table per concern; every agent reads from here.

- Length: WORD_RANGES is the only place word counts live. resolve_length_target()
  turns a request into the one target a post has; word_count_rule() is the only
  wording of it.
- Archetypes: ARCHETYPES holds every archetype's name, structure block and
  whether it needs a real event. A block describes structure only: no lengths,
  no diagram advice, no demand for details the sources may not have.
- Tone describes voice only. It never asks for a scene, a story or specifics.
"""

from dataclasses import dataclass
from typing import Any

# ── Length ────────────────────────────────────────────────────────────────────

# (min_words, max_words). Threads are measured in tweets and are not enforced.
WORD_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "linkedin post": {
        "concise":   (100, 180),
        "standard":  (250, 350),
        "long-form": (450, 600),
    },
    "medium article": {
        "concise":   (350, 500),
        "standard":  (700, 900),
        "long-form": (1200, 1800),
    },
}
THREAD_TWEETS: dict[str, tuple[int, int]] = {
    "concise":   (4, 6),
    "standard":  (7, 10),
    "long-form": (10, 15),
}
# A user's first post is short on purpose: a quick result that grabs attention.
FIRST_POST_RANGE = (70, 100)


def _normalise(value: str, default: str) -> str:
    return (value or default).lower().strip()


def resolve_length_target(
    format_type: str,
    length: str,
    *,
    first_post: bool = False,
    thin_sources: bool = False,
) -> dict[str, Any] | None:
    """The one length target for a post, or None for formats not measured in
    words (threads).

    {min_words, max_words, may_expand, basis}
    - basis "first_post": FIRST_POST_RANGE, whatever length was requested.
      Trimmed if over; never expanded.
    - basis "thin_sources" (low retrieval confidence): the requested range's
      ceiling with no floor. A short post is complete; never expanded.
    - basis "length_setting": the requested range; may be expanded up to its floor.
    """
    ranges = WORD_RANGES.get(_normalise(format_type, "linkedin post"))
    if ranges is None:
        return None
    if first_post:
        low, high = FIRST_POST_RANGE
        return {"min_words": low, "max_words": high, "may_expand": False, "basis": "first_post"}
    low, high = ranges.get(_normalise(length, "standard"), ranges["standard"])
    if thin_sources:
        return {"min_words": 0, "max_words": high, "may_expand": False, "basis": "thin_sources"}
    return {"min_words": low, "max_words": high, "may_expand": True, "basis": "length_setting"}


def word_count_rule(target: dict[str, Any] | None) -> str:
    """The length instruction for a writing prompt; "" when there is no target.

    The model is told the target, not asked to count: word_count_enforcer_node
    counts in code and trims or expands afterwards.
    """
    if not target:
        return ""
    high = target["max_words"]
    if target["min_words"]:
        return f"LENGTH: {target['min_words']}–{high} words. Never go over {high}."
    return (
        f"LENGTH: at most {high} words. A short post is complete: say what the sources "
        "support and stop. Never pad to reach a length."
    )


# ── Archetypes ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Archetype:
    name: str            # shown to the model as the post type
    fits: str            # one line for the selection prompt
    structure: str       # the block the drafter gets
    needs_event: bool = False   # only writable from a self-authored note that describes an event


_USE_WHAT_SOURCES_GIVE = (
    "Use the dates, places, names and numbers the sources give. "
    "Where they give none, write the point without one; never supply one."
)

GENERAL_ARCHETYPE = "general"

ARCHETYPES: dict[str, Archetype] = {
    "incident_report": Archetype(
        name="Incident Report / Retrospective",
        fits="something that went wrong in the author's own work and what it showed",
        needs_event=True,
        structure=(
            "Structure: Hook → Problem → Insight → Lesson → Action → Honesty.\n"
            "Tell only the incident the author's own notes describe. Include a section only if the notes "
            "cover it: if they record no action taken, there is no Action section.\n"
            "The Honesty section says what is still unresolved; it never ends optimistic.\n"
            + _USE_WHAT_SOURCES_GIVE
        ),
    ),
    "personal_story": Archetype(
        name="Personal Story",
        fits="a moment the author lived through and what it revealed",
        needs_event=True,
        structure=(
            "Structure: A specific moment → What you expected → What actually happened → "
            "What it revealed → One line that generalises.\n"
            "Tell only the moment the author's own notes describe. Start with a person, not a system or concept.\n"
            "The generalising line states what you now know, not what others should do.\n"
            + _USE_WHAT_SOURCES_GIVE
        ),
    ),
    "before_after": Archetype(
        name="Before & After",
        fits="a change the author made and what was different afterwards",
        needs_event=True,
        structure=(
            "Structure: State before → The thing that changed it → State after → What you'd tell yourself before.\n"
            "Tell only the change the author's own notes describe. Compact and chronological, no detours.\n"
            "The closing line is honest, not inspirational.\n"
            + _USE_WHAT_SOURCES_GIVE
        ),
    ),
    "contrarian_take": Archetype(
        name="Contrarian Take",
        fits="disagreeing with a common view; an opinion with reasons",
        structure=(
            "Structure: Bold falsifiable claim → The strongest version of the opposing view → "
            "The reasoning or evidence against it → Where the opposing view is right → Clear final position, no hedge.\n"
            "The opening claim must be specific enough that a reader can disagree with it.\n"
            "Evidence means what the sources contain. Where they contain none, argue from reasoning; "
            "never supply a statistic, study or example."
        ),
    ),
    "teach_me_something": Archetype(
        name="Teach Me Something",
        fits="explaining a concept or how something works",
        structure=(
            "Structure: Surprising premise → Core concept explained through one analogy → "
            "Why this matters beyond the obvious → One thing to try or watch for.\n"
            "The analogy carries the post: if it is weak, the post fails. An analogy is a comparison, "
            "not a story about something that happened.\n"
            "The premise must be something the target reader does not already know."
        ),
    ),
    "list_that_isnt": Archetype(
        name="List That Isn't",
        fits="several observations or lessons where one matters most",
        structure=(
            "Structure: Opens like a list, then subverts it: one item gets most of the space, "
            "or the last item contradicts the others.\n"
            "Works only with a real opinion about which item matters most.\n"
            "The subversion must be earned: the reader should feel surprised, not tricked."
        ),
    ),
    "prediction_bet": Archetype(
        name="Prediction / Bet",
        fits="a forward-looking view about where something is heading",
        structure=(
            "Structure: What I think is about to happen → Why most people don't see it yet (the signal) → "
            "What would follow from it → How you'll know if I'm wrong.\n"
            "The signal must be something observable that the sources or the request contain.\n"
            "State what would prove the prediction wrong.\n"
            "Say what the author is doing about it only if the sources or the request say so."
        ),
    ),
    GENERAL_ARCHETYPE: Archetype(
        name="General Post",
        fits="anything else, or when no other type clearly fits",
        structure=(
            "Structure: no fixed sections. Lead with the strongest point the sources support, "
            "develop it, and stop when it is made.\n"
            "Do not add a story, an example or a lesson to fill out a shape."
        ),
    ),
}

STORY_ARCHETYPES = frozenset(key for key, a in ARCHETYPES.items() if a.needs_event)


def get_archetype(archetype: str) -> Archetype:
    """The archetype for a key; an unknown key gets the neutral General Post."""
    return ARCHETYPES.get((archetype or "").lower().strip(), ARCHETYPES[GENERAL_ARCHETYPE])


# ── Format and tone ───────────────────────────────────────────────────────────

# Tone is voice only: word choice, register and rhythm. It never decides the
# post's structure, and never asks for a scene, a story or specifics.
_TONE = {
    "casual": (
        "Tone: casual and conversational. "
        "Write like you're texting a smart friend. "
        "Short sentences. Contractions are fine."
    ),
    "technical": (
        "Tone: technical and precise. "
        "Assume the reader is an engineer or builder. "
        "Use accurate terminology and state mechanisms exactly. "
        "Use the numbers and names the sources give; add none."
    ),
    "storytelling": (
        "Tone: narrative voice. "
        "Plain, vivid wording and sentences that pull the reader forward. "
        "This is how the post sounds, not what it contains: it does not license a scene, "
        "a moment or an event the sources don't describe."
    ),
}

_FORMAT = {
    "linkedin post": (
        "Format: LinkedIn post.\n"
        "Structure:\n"
        "  - Line 1: a single-sentence hook that stops the scroll. No clickbait.\n"
        "  - Body: short paragraphs (1–3 lines each), heavy line breaks.\n"
        "  - Closing: one sharp takeaway, question, or observation. No call-to-action.\n"
        "Do NOT use hashtags. Do NOT use bullet points with dashes — use line breaks instead.\n"
        "Do NOT write 'I' at the start of the first sentence.\n"
    ),
    "medium article": (
        "Format: Medium article.\n"
        "Structure:\n"
        "  - Opening: start with the point or the situation the sources describe, no slow intro.\n"
        "  - Use 3–5 subheadings (## style) to organize sections.\n"
        "  - Each section makes one point precisely.\n"
        "  - Closing: synthesis or call to rethink — not a summary.\n"
        "Technical depth is welcome. Use code snippets if relevant (markdown fenced blocks).\n"
    ),
    "thread": (
        "Format: Twitter/X Thread.\n"
        "Structure:\n"
        "  - Number each tweet: 1/, 2/, etc.\n"
        "  - Tweet 1: the hook — state the big idea or surprising fact.\n"
        "  - Tweets 2–(n-1): one insight or step per tweet, each standalone.\n"
        "  - Last tweet: the payoff — the lesson, the summary, the action.\n"
        "Each tweet must be under 280 characters. No filler tweets.\n"
    ),
}


def get_format_instructions(format_type: str, length: str, tone: str) -> str:
    """Format and tone instructions. Word length is not here (see
    word_count_rule); a thread gets its tweet count, which is not enforced."""
    fmt = _normalise(format_type, "linkedin post")
    parts = [_FORMAT.get(fmt, _FORMAT["linkedin post"])]
    if fmt == "thread":
        low, high = THREAD_TWEETS.get(_normalise(length, "standard"), THREAD_TWEETS["standard"])
        parts.append(f"Target: {low}–{high} tweets.")
    parts.append(_TONE.get(_normalise(tone, "casual"), _TONE["casual"]))
    return "\n".join(parts)
