import anthropic
import json
import os
from dotenv import load_dotenv

from pipeline.state import PipelineState

load_dotenv()

SYSTEM_PROMPT = """You are a content authenticity scorer. Score the following post on how much it reads like a real human wrote it — specifically a founder/builder with a strong, direct voice. Not polished corporate content. Not AI-generated filler. Real.

Score across exactly these 5 dimensions, each out of 20 points (total: 100):

1. Natural voice (0–20): Does it sound like a specific person talking? Does it have personality, opinions, or quirks? Or does it sound like a template?

2. Sentence variety (0–20): Is there rhythm and variation in sentence length? Short punches mixed with longer thoughts? Or is every sentence the same length and structure?

3. Specificity (0–20): Does it reference concrete details — real numbers, named examples, specific situations? Or does it deal in vague generalities?

4. No LLM fingerprints (0–20): Is it free from AI tells? No "In today's world", no "It's worth noting", no perfectly balanced lists of three, no corporate buzzwords, no passive voice chains?

5. Value delivery (0–20): Does the reader get something real — an insight, a lesson, a new way to see something? Or is it fluff?

Also identify up to 3 specific sentences that most hurt the score. These are the sentences that most need fixing.

Return ONLY valid JSON in exactly this format, nothing else:
{
  "total_score": <integer 0-100>,
  "dimension_scores": {
    "natural_voice": <integer 0-20>,
    "sentence_variety": <integer 0-20>,
    "specificity": <integer 0-20>,
    "no_llm_fingerprints": <integer 0-20>,
    "value_delivery": <integer 0-20>
  },
  "flagged_sentences": [
    "<sentence that hurts the score>",
    "<sentence that hurts the score>"
  ],
  "feedback": [
    "<one specific actionable note>",
    "<one specific actionable note>"
  ]
}"""


def scorer_node(state: PipelineState) -> PipelineState:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    current_draft = state["current_draft"]

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Score this post:\n\n{current_draft}",
            }
        ],
    )

    raw = message.content[0].text.strip()

    try:
        result = json.loads(raw)
        score = int(result.get("total_score", 0))
        feedback = result.get("feedback", [])
        flagged = result.get("flagged_sentences", [])
    except (json.JSONDecodeError, ValueError):
        # If JSON parsing fails, default to a low score to trigger retry
        score = 50
        feedback = ["Score parsing failed — retry to get fresh evaluation."]
        flagged = []

    state["score"] = score
    state["score_feedback"] = feedback + flagged
    return state
