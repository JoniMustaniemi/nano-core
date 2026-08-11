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
        description="Clear conversation and internal memory.",
    ),
    ToolCommand(
        id="capabilities",
        label="What can you do?",
        message="What can you do?",
        category="System",
        description="List Nano capabilities.",
    ),
    ToolCommand(
        id="open_brains",
        label="Open Brains",
        message="Open Brains.",
        category="Interface",
        description="Open the Brains activity view.",
        client_action="open_brains",
    ),
    ToolCommand(
        id="open_plans",
        label="Open Plans",
        message="Open Plans.",
        category="Interface",
        description="Open the Plans view.",
        client_action="open_plans",
    ),
    ToolCommand(
        id="open_storage",
        label="Open stored data",
        message="Open stored data.",
        category="Interface",
        description="Open the stored data view.",
        client_action="open_storage",
    ),
    ToolCommand(
        id="open_commands",
        label="Open commands",
        message="Open commands.",
        category="Interface",
        description="Open the commands view.",
        client_action="open_commands",
    ),
    ToolCommand(
        id="open_calendar",
        label="Open calendar",
        message="Show my calendar.",
        category="Calendar",
        description="Open the calendar view.",
        client_action="open_calendar",
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
