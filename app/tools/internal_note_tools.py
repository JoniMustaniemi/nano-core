from __future__ import annotations

from typing import Any

from app.memory import internal_notes
from app.memory.models import InternalNote
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _format_internal_note(note: InternalNote) -> str:
    lines = [f"{note.id}: [{note.status}] {note.title}"]
    content = note.content.strip()
    if content:
        lines.append(f"  {content}")
    return "\n".join(lines)


def _list_internal_notes(args: dict[str, Any]) -> str:
    """
    List Nano's private follow-up notes.

    Args:
        args: Tool argument dictionary.

    Returns:
        Human-readable internal note summary.
    """
    del args
    notes = internal_notes.list_internal_notes()
    if not notes:
        return "No internal notes saved."
    return "\n".join(_format_internal_note(note) for note in notes)


register_tool(
    ToolSpec(
        name="list_internal_notes",
        description="list Nano's private internal follow-up notes saved for later discussion.",
        args_schema={},
        handler=_list_internal_notes,
    )
)
