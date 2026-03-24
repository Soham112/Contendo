def get_archetype_instructions(archetype: str) -> str:
    """Return a detailed structural prompt block for the given archetype key."""
    archetype = archetype.lower().strip()

    instructions = {
        "incident_report": (
            "Structure: Hook → Problem → Insight → Lesson → Action → Honesty.\n"
            "Use case: Technical failures, production stories, build retrospectives.\n"
            "LinkedIn: 200–350 words. Keep every section lean — the HONESTY section must never feel optimistic or resolved.\n"
            "Thread: one tweet per section (6 tweets minimum).\n"
            "Article: expand the Problem and Insight sections with data, logs, or code snippets.\n"
            "Diagrams are encouraged when comparing before/after architecture or visualising a failure point."
        ),
        "contrarian_take": (
            "Structure: Bold falsifiable claim → Steel-man the consensus → 2–3 pieces of concrete evidence → "
            "Honest nuance where the consensus is right → Clear final position, no hedge.\n"
            "The opening claim must be specific enough that a reader can disagree with it.\n"
            "Steel-manning must be genuine — acknowledge the strongest version of the opposing view.\n"
            "LinkedIn: 200–350 words.\n"
            "No diagram unless directly comparing two things side by side."
        ),
        "personal_story": (
            "Structure: Specific moment in time → What you expected → What actually happened → "
            "What it revealed → One line that generalises.\n"
            "The post must start with a person, not a system or concept.\n"
            "The 'specific moment' must be dated or located — give it a when or a where.\n"
            "The generalising line at the end should not moralize — state what you now know, not what others should do.\n"
            "LinkedIn: 150–300 words.\n"
            "No diagram."
        ),
        "teach_me_something": (
            "Structure: Surprising premise → Core concept explained through one concrete analogy → "
            "Why this matters beyond the obvious → One thing to try or watch for.\n"
            "The analogy is the load-bearing element — if the analogy is weak, the post fails.\n"
            "The 'surprising premise' must be something the target reader does not already know.\n"
            "LinkedIn: 200–400 words.\n"
            "Diagram or image is recommended when it can make the analogy visual — only include if it genuinely adds clarity."
        ),
        "list_that_isnt": (
            "Structure: Opens like a listicle, then subverts it — one item gets most of the space, "
            "or the last item contradicts the others.\n"
            "Works only when the writer has a genuine opinion about which item matters most.\n"
            "The subversion must be earned — the reader should feel surprised, not tricked.\n"
            "LinkedIn: 150–300 words.\n"
            "No diagram."
        ),
        "prediction_bet": (
            "Structure: What I think is about to happen → Why most people don't see it yet "
            "(the specific signal) → What I'm doing about it → How you'll know if I'm wrong.\n"
            "The 'specific signal' is the hardest and most important part — it must be something observable, not vague.\n"
            "The last section must state a concrete falsifiability condition — what would prove this prediction wrong.\n"
            "Stakes the writer's credibility explicitly.\n"
            "LinkedIn: 200–350 words.\n"
            "Diagram only if visualising a trend line or timeline — skip otherwise."
        ),
        "before_after": (
            "Structure: State before → The thing that changed it (decision, tool, or realisation) → "
            "State after → What you'd tell yourself before.\n"
            "Compact, chronological, personal — no detours.\n"
            "The 'thing that changed it' must be specific: name the tool, the conversation, the moment, or the number.\n"
            "The 'what you'd tell yourself before' must be honest, not inspirational.\n"
            "LinkedIn: 150–280 words.\n"
            "No diagram unless comparing tools or architectures directly."
        ),
    }

    return instructions.get(archetype, instructions["incident_report"])


def get_format_instructions(format_type: str, tone: str) -> str:
    format_type = format_type.lower().strip()
    tone = tone.lower().strip()

    tone_map = {
        "casual": (
            "Tone: casual and conversational. "
            "Write like you're texting a smart friend. "
            "Short sentences. Contractions are fine. First-person."
        ),
        "technical": (
            "Tone: technical and precise. "
            "Assume the reader is an engineer or builder. "
            "Use accurate terminology. Show, don't just tell. "
            "Include specifics — numbers, names, mechanisms."
        ),
        "storytelling": (
            "Tone: narrative and story-driven. "
            "Open with a scene or moment, not a thesis. "
            "Build tension. End with a lesson learned or insight earned."
        ),
    }
    tone_instruction = tone_map.get(tone, tone_map["casual"])

    format_map = {
        "linkedin post": (
            "Format: LinkedIn post.\n"
            "Length: 150–300 words.\n"
            "Structure:\n"
            "  - Line 1: a single-sentence hook that stops the scroll. No clickbait.\n"
            "  - Body: short paragraphs (1–3 lines each), heavy line breaks.\n"
            "  - Closing: one sharp takeaway, question, or observation. No call-to-action.\n"
            "Do NOT use hashtags. Do NOT use bullet points with dashes — use line breaks instead.\n"
            "Do NOT write 'I' at the start of the first sentence.\n"
        ),
        "medium article": (
            "Format: Medium article.\n"
            "Length: 600–1000 words.\n"
            "Structure:\n"
            "  - Opening: drop into the middle of a situation or insight, no slow intro.\n"
            "  - Use 3–5 subheadings (## style) to organize sections.\n"
            "  - Each section: 100–200 words, concrete and specific.\n"
            "  - Closing: synthesis or call to rethink — not a summary.\n"
            "Technical depth is welcome. Use code snippets if relevant (markdown fenced blocks).\n"
        ),
        "thread": (
            "Format: Twitter/X Thread.\n"
            "Length: 6–10 tweets.\n"
            "Structure:\n"
            "  - Number each tweet: 1/, 2/, etc.\n"
            "  - Tweet 1: the hook — state the big idea or surprising fact.\n"
            "  - Tweets 2–(n-1): one insight or step per tweet, each standalone.\n"
            "  - Last tweet: the payoff — the lesson, the summary, the action.\n"
            "Each tweet must be under 280 characters. No filler tweets.\n"
        ),
    }
    format_instruction = format_map.get(format_type, format_map["linkedin post"])

    return f"{format_instruction}\n{tone_instruction}"
