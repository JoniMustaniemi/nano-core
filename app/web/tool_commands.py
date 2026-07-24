from __future__ import annotations

from dataclasses import asdict, dataclass

from app.tools.registry import list_ui_tool_commands


@dataclass(frozen=True, slots=True)
class ToolCommand:
    """User-facing quick command for the web UI."""

    id: str
    label: str
    message: str
    category: str
    description: str = ""
    client_action: str = ""


EXTRA_UI_COMMANDS: tuple[ToolCommand, ...] = (
    ToolCommand(
        id="wipe_data",
        label="Wipe data",
        message="Wipe your data.",
        category="System",
        description="Clear all stored notes, reminders, conversation, and internal memory.",
    ),
    ToolCommand(
        id="capabilities",
        label="What can you do?",
        message="What can you do?",
        category="System",
        description="List Nano capabilities.",
    ),
    ToolCommand(
        id="toggle_controls",
        label="Hide/show controls",
        message="Hide controls.",
        category="Interface",
        description="Toggle footer controls for a focused view.",
        client_action="toggle_controls",
    ),
)


def _tool_commands_from_registry() -> tuple[ToolCommand, ...]:
    commands: list[ToolCommand] = []
    for tool in list_ui_tool_commands():
        commands.append(
            ToolCommand(
                id=tool.name,
                label=tool.ui_label or tool.name,
                message=tool.ui_message or "",
                category=tool.ui_category or "Tools",
                description=tool.ui_description,
            )
        )
    return tuple(commands)


def list_tool_commands() -> list[dict[str, str]]:
    """
    Return tool commands for the web UI.

    Returns:
        Serializable command definitions grouped by category.
    """
    commands = (*_tool_commands_from_registry(), *EXTRA_UI_COMMANDS)
    return [asdict(command) for command in commands]
