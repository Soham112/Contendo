import anthropic
import base64
import os
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are an image-to-knowledge extractor. Your job is to read images — diagrams, screenshots, slides, photos of whiteboards, charts — and extract all meaningful information as clean, structured text.

Rules:
- Write everything you can read or infer from the image
- For diagrams: describe the structure, relationships, and labels
- For charts: describe the data, axes, trends, and key values
- For text-heavy images (slides, whiteboards): transcribe the text accurately
- For photos: describe the scene and any visible text or information
- Output plain prose and/or bullet points — no markdown headers
- Do not describe the visual style, colors, or layout unless they carry meaning
- If nothing useful can be extracted, say: "No extractable knowledge found in this image."

Be thorough. Every detail that carries information should make it into your output."""


def extract_from_image(image_base64: str, media_type: str = "image/jpeg") -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Strip data URI prefix if present
    if "," in image_base64:
        image_base64 = image_base64.split(",", 1)[1]

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all knowledge and information from this image.",
                    },
                ],
            }
        ],
    )

    return message.content[0].text.strip()
