from __future__ import annotations

import json
from typing import Any

from app.assistant.agent_types import Decision


def parse_decision(raw: str) -> Decision:
    """
    Parse decision.

    Args:
        raw: Raw input value to parse.

    Returns:
        Decision result.
    """
    payload = extract_json(raw)
    if isinstance(payload, dict):
        decision_type = payload.get("type")
        if decision_type in {"final", "answer_intent"}:
            content = payload.get("content")
            if isinstance(content, str) and content.strip():
                if decision_type == "final":
                    return {"type": "final", "content": content}
                return {"type": "answer_intent", "content": content}
            if decision_type == "answer_intent":
                return {"type": "answer_intent"}
        if decision_type == "tool_call":
            tool = payload.get("tool")
            args = payload.get("args", {})
            if isinstance(tool, str) and isinstance(args, dict):
                return {"type": "tool_call", "tool": tool, "args": args}
    return {"type": "invalid"}


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


def extract_json(raw: str) -> Any:
    """
    Extract json.

    Args:
        raw: Raw input value to parse.

    Returns:
        Any result.
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
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
