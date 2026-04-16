import anthropic
import os
import re
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=3,
)

STYLE_VARIANTS = [
    {
        "name": "flowchart",
        "description": "Left-to-right flowchart with rounded rectangles and directional arrows. Color: sage greens and warm greys.",
    },
    {
        "name": "layered",
        "description": "Horizontal stacked layers like an architecture diagram. Each layer a different muted tone. Labels left-aligned.",
    },
    {
        "name": "radial",
        "description": "Central concept with spokes radiating outward to connected nodes. Clean circular layout.",
    },
    {
        "name": "timeline",
        "description": "Left-to-right timeline with nodes on a horizontal spine. Dates or steps above, descriptions below.",
    },
    {
        "name": "comparison",
        "description": "Two or three column comparison layout. Each column a distinct muted color. Headers bold at top.",
    },
]

DIAGRAM_PROMPT = """Generate a clean SVG diagram for the following concept:
{description}

Visual style: {style_description}

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

REFINE_PROMPT = """You are refining an existing SVG diagram based on a user instruction.

Original diagram description:
{description}

Current SVG:
{current_svg}

Refinement instruction:
{instruction}

Modify the diagram based on this instruction. Keep the same viewBox and self-contained SVG rules. Output only raw SVG."""


def _select_style_variant(description: str) -> dict:
    desc_lower = description.lower()
    if any(word in desc_lower for word in ["flow", "process", "pipeline", "steps", "step"]):
        return next(v for v in STYLE_VARIANTS if v["name"] == "flowchart")
    if any(word in desc_lower for word in ["layer", "stack", "architecture", "infrastructure"]):
        return next(v for v in STYLE_VARIANTS if v["name"] == "layered")
    if any(word in desc_lower for word in ["compare", "vs", "versus", "difference", "comparison"]):
        return next(v for v in STYLE_VARIANTS if v["name"] == "comparison")
    if any(word in desc_lower for word in ["timeline", "history", "evolution", "over time"]):
        return next(v for v in STYLE_VARIANTS if v["name"] == "timeline")
    return next(v for v in STYLE_VARIANTS if v["name"] == "radial")


def _strip_svg(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()
    if not raw.startswith("<svg"):
        raise ValueError("Claude returned malformed SVG — does not start with <svg")
    return raw


def generate_svg_for_diagram(
    description: str,
    style_hint: str | None = None,
    current_svg: str | None = None,
    refinement_instruction: str | None = None,
) -> str:
    """Generate or refine an SVG diagram.

    Args:
        description: The original diagram description.
        style_hint: Optional explicit style description (overrides auto-selection).
        current_svg: For refinement — the existing SVG to modify.
        refinement_instruction: For refinement — what to change.
    """
    if refinement_instruction and current_svg:
        prompt = REFINE_PROMPT.format(
            description=description,
            current_svg=current_svg,
            instruction=refinement_instruction,
        )
    else:
        style_description = style_hint or _select_style_variant(description)["description"]
        prompt = DIAGRAM_PROMPT.format(
            description=description,
            style_description=style_description,
        )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return _strip_svg(message.content[0].text)


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


def generate_visuals(post_content: str) -> list[dict]:
    placeholders = _parse_placeholders(post_content)
    visuals = []

    for item in placeholders:
        if item["type"] == "DIAGRAM":
            try:
                svg_code = generate_svg_for_diagram(item["description"])
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
