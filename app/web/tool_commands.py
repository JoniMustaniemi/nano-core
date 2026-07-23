from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ToolCommand:
    """User-facing quick command for the web UI."""

    id: str
    label: str
    message: str
    category: str
    description: str = ""


TOOL_COMMANDS: tuple[ToolCommand, ...] = (
    ToolCommand(
        id="check_health",
        label="Health check",
        message="Check your health.",
        category="System",
        description="Run Nano diagnostics.",
    ),
    ToolCommand(
        id="wipe_data",
        label="Wipe data",
        message="Wipe your data.",
        category="System",
        description="Clear all stored notes, reminders, conversation, and internal memory.",
    ),
    ToolCommand(
        id="add_note",
        label="Add note",
        message="Add a note.",
        category="Notes",
        description="Save a new note.",
    ),
    ToolCommand(
        id="list_notes",
        label="List notes",
        message="List my notes.",
        category="Notes",
        description="Show saved notes.",
    ),
    ToolCommand(
        id="list_internal_notes",
        label="Internal notes",
        message="Tell me about your internal notes.",
        category="Notes",
        description="Show Nano's private follow-up notes.",
    ),
    ToolCommand(
        id="start_timer",
        label="Start 5 min timer",
        message="Start a 5 minute timer.",
        category="Timers",
        description="Set a five-minute countdown.",
    ),
    ToolCommand(
        id="list_timers",
        label="Active timers",
        message="Check active timers.",
        category="Timers",
        description="Show running timers.",
    ),
    ToolCommand(
        id="cancel_timers",
        label="Cancel timers",
        message="Cancel timers.",
        category="Timers",
        description="Stop active timers.",
    ),
    ToolCommand(
        id="list_reminders",
        label="List reminders",
        message="List reminders.",
        category="Reminders",
        description="Show scheduled reminders.",
    ),
    ToolCommand(
        id="create_pull_request",
        label="Create pull request",
        message="Create a pull request.",
        category="GitHub",
        description="Open a PR for current changes.",
    ),
    ToolCommand(
        id="propose_self_changes",
        label="Propose self-improvement",
        message="Improve yourself by making timer messages clearer.",
        category="GitHub",
        description="Analyze Nano's code and open a self-improvement PR.",
    ),
    ToolCommand(
        id="capabilities",
        label="What can you do?",
        message="What can you do?",
        category="System",
        description="List Nano capabilities.",
    ),
)


def list_tool_commands() -> list[dict[str, str]]:
    """
    Return tool commands for the web UI.

    Returns:
        Serializable command definitions grouped by category.
    """
    return [asdict(command) for command in TOOL_COMMANDS]
