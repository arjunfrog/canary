"""The photo reader: turns a leak image into questions, numbers and option order.

To build (task 5 in docs/PROMPTS.md), with Gemini vision and a strict JSON schema.
Only leak images are ever sent. The question bank never is.
"""


def read_image(image: bytes, api_key: str) -> dict:
    """Return {"questions": [{number, legible, stem, options, stem_en, options_en}]}."""
    raise NotImplementedError("task 5: read_image")
