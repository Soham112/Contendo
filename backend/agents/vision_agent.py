"""Reads an image: the text written in it, and separately what it shows.

The two are kept apart so provenance (step 3.3) can treat them differently:
transcribed text is what the image says; the description is the model's
reading of it and may include interpretation.
"""
from pydantic import BaseModel, Field

from llm.client import SONNET, complete_structured

# Bump when SYSTEM_PROMPT, the schema or the model changes (recorded per source).
# 2: transcription and description returned separately; no inference asked for.
EXTRACTOR = ("vision_agent", "2")

SYSTEM_PROMPT = """You read images people save to their knowledge base: photos of handwritten notes, slides, screenshots of posts or documents, diagrams, charts, whiteboards and ordinary photos.

Return two things, kept strictly apart:

transcribed_text: every piece of text that is written or printed in the image, exactly as it appears, in reading order. Put each separate line, list item and label on its own line. Only for a real table (rows and columns), write each row as its cells separated by " | ". Do not correct, complete, translate or summarise the text. If a word is unreadable, write [unreadable] in its place. If the image contains no text, return an empty string.

description: what the image shows that the text alone does not carry, in plain sentences: the structure of a diagram (which boxes connect to which, what the arrows mean), what a chart plots (axes, series, the values it shows), and what a photo depicts. Describe only what is visible. Do not guess at names, dates, numbers, places or intentions that are not shown, and do not restate the transcribed text. Leave out visual style (colours, fonts, backgrounds, layout, icons) unless it carries meaning. If the image is text on a plain design, such as a slide, a document or a screenshot of a post, and shows nothing beyond its text, return an empty string."""


class ImageReading(BaseModel):
    transcribed_text: str = Field(description="Text written or printed in the image, verbatim, in reading order")
    description: str = Field(description="What the image shows beyond its text; only what is visible")


def read_image(image_base64: str, media_type: str = "image/jpeg", *, user_id: str) -> ImageReading:
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]   # strip a data URI prefix
    return complete_structured(
        schema=ImageReading,
        tool_name="record_image_reading",
        tool_description="Record the image's transcribed text and its description, kept apart.",
        model=SONNET,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_base64}},
                {"type": "text", "text": "Read this image."},
            ],
        }],
        user_id=user_id,
        event_type="vision_extract",
    )
