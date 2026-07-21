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


def extract_json(raw: str) -> Any:
    """
    Extract json.

    Args:
        raw: Raw input value to parse.

    Returns:
        Any result.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
