from __future__ import annotations

from typing import Any

from app.memory import repository
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _add_note(args: dict[str, Any]) -> str:
    """
    Add note.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    name = str(args.get("name", "Untitled note"))
    content = str(args.get("content", ""))
    note = repository.add_note(content, name=name)
    return f"saved note {note.id} ({note.name}): {note.content}"


def _list_notes(args: dict[str, Any]) -> str:
    """
    List notes.

    Args:
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    del args
    notes = repository.list_notes()
    return "\n".join(f"{note.id}: {note.name} - {note.content}" for note in notes) or "No notes."


register_tool(
    ToolSpec(
        name="add_note",
        description="save a note.",
        args_schema={
            "name": "Short name for the note.",
            "content": "The note text to store.",
        },
        handler=_add_note,
        announcement="Saving that to memory.",
        keywords=("note", "remember", "write down", "save this"),
        ui_label="Add note",
        ui_message="Add a note.",
        ui_category="Notes",
        ui_description="Save a new note.",
    )
)

register_tool(
    ToolSpec(
        name="list_notes",
        description="list recent notes.",
        args_schema={},
        handler=_list_notes,
        announcement="Checking memory.",
        keywords=("notes", "note", "remembered"),
        ui_label="List notes",
        ui_message="List my notes.",
        ui_category="Notes",
        ui_description="Show saved notes.",
    )
)
