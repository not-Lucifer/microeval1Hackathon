"""Extract the final JSON answer from a model reply.

Rule (stated in the system prompt): the LAST fenced ```json block is the answer. If the
reply has no such block, fall back to the last top-level JSON object in the text. Any
failure becomes PARSE_ERROR at grading time; the raw text is always kept in the transcript.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

# A block opens only with ```json at the start of a line (leading spaces allowed), as in
# Markdown, so a sentence that merely mentions "```json" does not swallow the real answer.
JSON_FENCE = re.compile(r"^[ \t]*```json[^\n]*\n(.*?)```", re.DOTALL | re.IGNORECASE | re.MULTILINE)


def last_top_level_object(text: str) -> Optional[dict]:
    """Scan left to right, decoding a JSON object at each '{' that is not inside an object
    already decoded; return the last one (so nested objects are never mistaken for it)."""
    decoder = json.JSONDecoder()
    found, i = None, 0
    while True:
        i = text.find("{", i)
        if i < 0:
            return found
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict):
            found = obj
        i = end


def extract_final_json(text: str) -> tuple[Optional[Any], Optional[str]]:
    """Returns ``(value, None)`` on success or ``(None, error message)``."""
    blocks = JSON_FENCE.findall(text or "")
    if blocks:
        try:
            return json.loads(blocks[-1]), None
        except json.JSONDecodeError as exc:
            return None, f"last ```json block is not valid JSON: {exc}"
    obj = last_top_level_object(text or "")
    if obj is None:
        return None, "no ```json block and no JSON object found"
    return obj, None
