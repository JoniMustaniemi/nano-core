from __future__ import annotations

from app.assistant.agent_types import Decision
from app.common.json_parsing import extract_json, looks_like_truncated_json

__all__ = ["extract_json", "looks_like_truncated_json", "parse_decision"]


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
