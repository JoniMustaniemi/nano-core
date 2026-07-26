from __future__ import annotations

import json
from typing import Any


def _find_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _strip_markdown_fence(text: str) -> str:
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    return text


def looks_like_truncated_json(raw: str) -> bool:
    """
    Return True when raw text appears to start JSON but never closes an object.

    Args:
        raw: Raw model output to inspect.

    Returns:
        True when a JSON object looks cut off before completion.
    """
    if not isinstance(raw, str):
        return False
    text = _strip_markdown_fence(raw.strip())
    if "{" not in text:
        return False
    return _find_balanced_json_object(text) is None


def extract_json(raw: str) -> Any:
    """
    Extract json.

    Args:
        raw: Raw input value to parse.

    Returns:
        Parsed JSON value, or None when parsing fails.
    """
    if not isinstance(raw, str):
        return None
    text = _strip_markdown_fence(raw.strip())
    balanced = _find_balanced_json_object(text)
    if balanced is not None:
        text = balanced
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
