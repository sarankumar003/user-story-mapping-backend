"""
Utility to sanitize and repair near-JSON text from LLMs into valid JSON strings.
"""

import re
from typing import Tuple


def sanitize_and_repair(raw_text: str) -> Tuple[str, list]:
    """Best-effort repair for common JSON issues produced by LLMs.
    Returns (clean_json_text, warnings).
    Steps:
      - strip code fences and leading/trailing noise
      - normalize smart quotes
      - remove BOM, carriage returns
      - collapse accidental line-breaks inside strings
      - remove trailing commas
      - ensure top-level braces
    """
    warnings = []

    if raw_text is None:
        return "{}", ["empty"]

    text = raw_text

    # Remove BOM and carriage returns
    text = text.replace("\ufeff", "").replace("\r", "")

    # Strip code fences if present
    t = text.strip()
    if t.startswith("```"):
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end != -1:
            text = t[start : end + 1]
            warnings.append("removed_code_fences")

    # Normalize smart quotes
    replacements = {
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
        "“": '"', "”": '"', "‘": "'", "’": "'",
    }
    for k, v in replacements.items():
        if k in text:
            text = text.replace(k, v)
            warnings.append("normalized_quotes")

    # Remove trailing commas before } or ]
    new_text = re.sub(r",\s*([}\]])", r"\1", text)
    if new_text != text:
        text = new_text
        warnings.append("removed_trailing_commas")

    # Ensure it looks like a JSON object
    if "{" in text and "}" in text:
        start = text.find("{")
        end = text.rfind("}")
        text = text[start : end + 1]

    return text, warnings







