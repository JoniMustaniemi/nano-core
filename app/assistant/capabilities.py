from __future__ import annotations

from dataclasses import dataclass

from app.tools import list_tools


@dataclass(frozen=True, slots=True)
class CapabilityItem:
    """User-facing capability derived from a tool or built-in interaction."""

    name: str
    description: str


_EXTRA_CAPABILITIES: tuple[CapabilityItem, ...] = (
    CapabilityItem(
        name="conversation",
        description="answer questions and hold conversation without calling tools when appropriate.",
    ),
    CapabilityItem(
        name="memory_wipe",
        description=(
            "clear chat history, internal notes, improvement plans, "
            "and codebase memory after explicit confirmation."
        ),
    ),
)

_CAPABILITY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Memory",
        ("list_internal_notes", "memory_wipe", "conversation"),
    ),
    (
        "Timers",
        ("start_timer", "list_timers", "cancel_timers"),
    ),
    (
        "Files and code",
        ("read_file", "write_file", "list_files", "run_python"),
    ),
    (
        "Diagnostics and GitHub",
        ("check_health", "create_pull_request", "draft_improvement_plan"),
    ),
)


def list_capability_items() -> list[CapabilityItem]:
    """
    Return the current capability catalog for user-facing answers.

    Returns:
        Sorted capability items from registered tools plus built-in interactions.
    """
    tool_items = [
        CapabilityItem(name=tool.name, description=tool.description) for tool in list_tools()
    ]
    return sorted([*tool_items, *_EXTRA_CAPABILITIES], key=lambda item: item.name)


def format_capability_catalog() -> str:
    """
    Format the capability catalog as factual payload text.

    Returns:
        Multi-line grouped catalog for answer drafting prompts.
    """
    items = {item.name: item for item in list_capability_items()}
    lines = ["Available capabilities (grouped):"]
    placed: set[str] = set()

    for group_name, names in _CAPABILITY_GROUPS:
        group_lines: list[str] = []
        for name in names:
            item = items.get(name)
            if item is None:
                continue
            group_lines.append(f"  - {item.name}: {item.description}")
            placed.add(item.name)
        if group_lines:
            lines.append(f"{group_name}:")
            lines.extend(group_lines)

    remaining = [item for name, item in sorted(items.items()) if name not in placed]
    if remaining:
        lines.append("Other:")
        lines.extend(f"  - {item.name}: {item.description}" for item in remaining)

    return "\n".join(lines)
