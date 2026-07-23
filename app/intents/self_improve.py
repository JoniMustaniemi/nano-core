"""Shared intent helpers with no assistant-layer dependencies."""

from __future__ import annotations

VAGUE_SELF_IMPROVE_GOALS = frozenset({
    "",
    "general improvement",
    "improve yourself",
    "fix yourself",
    "update yourself",
    "modify yourself",
})


def is_vague_self_improve_goal(goal: str) -> bool:
    normalized = " ".join(goal.strip().split()).lower()
    return normalized in VAGUE_SELF_IMPROVE_GOALS
