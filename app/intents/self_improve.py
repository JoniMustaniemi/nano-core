"""Shared intent helpers with no assistant-layer dependencies."""

from __future__ import annotations

import re

_DRAFT_PLAN_PREFIX = re.compile(
    r"^draft(?:ing)?\s+(?:an?\s+)?improvement\s+plan\s+(?:for|about|on)\s+",
    re.IGNORECASE,
)
_IMPROVE_SELF_PREFIX = re.compile(
    r"^(?:improve|fix|update|modify)\s+(?:yourself|your\s+code|nano)(?:\s+(?:by|to))?\s+",
    re.IGNORECASE,
)

VAGUE_SELF_IMPROVE_GOALS = frozenset({
    "",
    "general improvement",
    "improve yourself",
    "fix yourself",
    "update yourself",
    "modify yourself",
})


def normalize_self_improve_goal(goal: str) -> str:
    """Strip meta phrasing so goals read like themes, not tool instructions."""
    cleaned = " ".join(goal.strip().rstrip(".").split())
    if not cleaned:
        return cleaned
    for pattern in (_DRAFT_PLAN_PREFIX, _IMPROVE_SELF_PREFIX):
        cleaned = pattern.sub("", cleaned).strip()
    return cleaned


def is_vague_self_improve_goal(goal: str) -> bool:
    normalized = normalize_self_improve_goal(goal).lower()
    return normalized in VAGUE_SELF_IMPROVE_GOALS
