import anthropic
import os
import re
from dotenv import load_dotenv

load_dotenv()

DIAGRAM_PROMPT = """Generate a clean SVG diagram for the following concept:
{description}

Requirements:
- viewBox must be '0 0 680 400' or taller if needed
- Light white or off-white background
- Use colored rounded rectangles for components
- Use arrows with clear direction to show flow
- Bold title at the top describing the diagram
- Color code by category — same type of component gets the same color
- Clean sans-serif labels on every component
- Group related components inside dashed border containers
- Maximum 12 components — keep it readable
- No gradients, no shadows, no decorative elements
- No external fonts, no external images, no CDN links — fully self-contained SVG
- Output ONLY the raw SVG code starting with <svg — no explanation, no markdown, no backticks"""


def _parse_placeholders(post_content: str) -> list[dict]:
    pattern = r'\[(DIAGRAM|IMAGE):([^\]]+)\]'
    matches = list(re.finditer(pattern, post_content, re.IGNORECASE))
    results = []
    for position, match in enumerate(matches):
        kind = match.group(1).upper()
        description = match.group(2).strip()
        results.append({
            "type": kind,
            "description": description,
            "position": position,
            "placeholder": match.group(0),
        })
    return results


def _generate_svg(description: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": DIAGRAM_PROMPT.format(description=description),
            }
        ],
    )
    raw = message.content[0].text.strip()

    # Strip markdown code fences if Claude wrapped the SVG
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    if not raw.startswith("<svg"):
        raise ValueError(f"Claude returned malformed SVG — does not start with <svg")

    return raw


def generate_visuals(post_content: str) -> list[dict]:
    placeholders = _parse_placeholders(post_content)
    visuals = []

    for item in placeholders:
        if item["type"] == "DIAGRAM":
            try:
                svg_code = _generate_svg(item["description"])
                visuals.append({
                    "type": "diagram",
                    "placeholder": item["placeholder"],
                    "description": item["description"],
                    "position": item["position"],
                    "svg_code": svg_code,
                    "reminder_text": None,
                })
            except Exception:
                visuals.append({
                    "type": "diagram",
                    "placeholder": item["placeholder"],
                    "description": item["description"],
                    "position": item["position"],
                    "svg_code": None,
                    "reminder_text": None,
                })
        else:  # IMAGE
            reminder = (
                f"Add a visual here: {item['description']}. "
                f"Use a real photo, screenshot, or data chart that shows this directly."
            )
            visuals.append({
                "type": "image_reminder",
                "placeholder": item["placeholder"],
                "description": item["description"],
                "position": item["position"],
                "svg_code": None,
                "reminder_text": reminder,
            })

    return visuals
