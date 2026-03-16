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
