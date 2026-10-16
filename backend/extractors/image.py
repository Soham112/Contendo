"""An image: one vision call (agents/vision_agent.py), its two parts stored as
two headed sections so they stay apart in the text and later in chunks:

    # Text in the image      what is written in it, verbatim
    # What the image shows   the model's description

Either section is left out when empty. The title is derived: the first line of
the text, else of the description.
"""
from __future__ import annotations

from agents.vision_agent import EXTRACTOR, read_image
from extractors import Extraction, ExtractionError
from memory.source_store import uploaded

TEXT_HEADING = "# Text in the image"
DESCRIPTION_HEADING = "# What the image shows"
_TITLE_CHARS = 80


def _title(reading) -> str:
    for part in (reading.transcribed_text, reading.description):
        for line in part.splitlines():
            if line.strip():
                line = line.strip()
                return line if len(line) <= _TITLE_CHARS else line[:_TITLE_CHARS] + "…"
    return "Image"


def extract_image(data: bytes, image_base64: str, media_type: str, *, user_id: str) -> Extraction:
    reading = read_image(image_base64, media_type=media_type, user_id=user_id)
    sections = []
    if reading.transcribed_text.strip():
        sections.append(f"{TEXT_HEADING}\n\n{reading.transcribed_text.strip()}")
    if reading.description.strip():
        sections.append(f"{DESCRIPTION_HEADING}\n\n{reading.description.strip()}")
    if not sections:
        raise ExtractionError("No text or content could be read from this image.")
    return Extraction(
        text="\n\n".join(sections),
        title=_title(reading),
        original=uploaded("image", data=data, mime=media_type, extractor=EXTRACTOR, title_provided=False),
        metadata={"has_text": bool(reading.transcribed_text.strip())},
    )
