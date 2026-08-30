from __future__ import annotations

from app.timers import operations
from app.tools.base import ToolSpec
from app.tools.registry import register_tool

register_tool(
    ToolSpec(
        name="start_timer",
        description=(
            "start or add a timer for a specific duration; use this only when the user has "
            "given an explicit time length."
        ),
        args_schema={
            "duration_seconds": "Length of the timer in seconds.",
            "duration_minutes": "Optional length of the timer in minutes.",
            "duration_hours": "Optional length of the timer in hours.",
            "duration_text": "Optional natural duration like 30s or 2min.",
            "label": "Optional short timer label.",
        },
        handler=operations.start_timer,
        announcement="Starting a timer.",
        keywords=("timer", "countdown", "add timer", "start timer", "set timer"),
        ui_label="Add timer",
        ui_message="Add a timer.",
        ui_category="Timers",
        ui_description="Start or add a countdown timer.",
    )
)

register_tool(
    ToolSpec(
        name="start_stopwatch",
        description="start a stopwatch that counts up until stopped.",
        args_schema={
            "label": "Optional short stopwatch label.",
        },
        handler=operations.start_stopwatch,
        announcement="Starting a stopwatch.",
        keywords=("stopwatch", "stop watch", "start stopwatch", "add stopwatch"),
        ui_label="Start stopwatch",
        ui_message="Start a stopwatch.",
        ui_category="Timers",
        ui_description="Start a count-up stopwatch.",
    )
)

register_tool(
    ToolSpec(
        name="list_timers",
        description="list timers and stopwatches that have been created through the timer tools.",
        args_schema={},
        handler=operations.list_timers,
        announcement="Checking timers.",
        keywords=("timer", "timers", "stopwatch", "stopwatches"),
    )
)

register_tool(
    ToolSpec(
        name="cancel_timers",
        description="cancel active countdown timers that were created through the timer tool.",
        args_schema={
            "timer_id": "Optional timer id to cancel. If omitted, cancel all active timers.",
            "label": "Optional timer label to cancel. If omitted, cancel all active timers.",
        },
        handler=operations.cancel_timers,
        announcement="Cancelling timers.",
        keywords=("timer", "timers", "countdown"),
        ui_label="Cancel timers",
        ui_message="Cancel timers.",
        ui_category="Timers",
        ui_description="Stop active countdown timers.",
    )
)

register_tool(
    ToolSpec(
        name="stop_stopwatches",
        description="stop active stopwatches that were created through the stopwatch tool.",
        args_schema={
            "stopwatch_id": "Optional stopwatch id to stop. If omitted, stop all active stopwatches.",
            "label": "Optional stopwatch label to stop. If omitted, stop all active stopwatches.",
        },
        handler=operations.stop_stopwatches,
        announcement="Stopping stopwatches.",
        keywords=("stopwatch", "stopwatches", "stop watch"),
        ui_label="Stop stopwatch",
        ui_message="Stop stopwatch.",
        ui_category="Timers",
        ui_description="Stop active stopwatches.",
    )
)

register_tool(
    ToolSpec(
        name="rename_timer",
        description="rename one active countdown timer without changing its remaining time.",
        args_schema={
            "timer_id": "Timer id to rename.",
            "label": "Current timer label when id is omitted.",
            "new_label": "New timer label.",
        },
        handler=operations.rename_timer,
        announcement="Renaming timer.",
        keywords=("rename", "change name", "timer"),
        ui_label="Rename timer",
        ui_message="Rename timer.",
        ui_category="Timers",
        ui_description="Rename one active countdown timer.",
    )
)

register_tool(
    ToolSpec(
        name="rename_stopwatch",
        description="rename one active stopwatch without changing its elapsed time.",
        args_schema={
            "stopwatch_id": "Stopwatch id to rename.",
            "label": "Current stopwatch label when id is omitted.",
            "new_label": "New stopwatch label.",
        },
        handler=operations.rename_stopwatch,
        announcement="Renaming stopwatch.",
        keywords=("rename", "change name", "stopwatch", "stop watch"),
        ui_label="Rename stopwatch",
        ui_message="Rename stopwatch.",
        ui_category="Timers",
        ui_description="Rename one active stopwatch.",
    )
)

register_tool(
    ToolSpec(
        name="clear_all_timers",
        description=(
            "clear all active countdown timers and stopwatches created through the timer tools."
        ),
        args_schema={},
        handler=operations.clear_all_timers,
        announcement="Clearing all timers.",
        keywords=("timer", "timers", "clear all timers", "delete all timers"),
        ui_label="Clear all timers",
        ui_message="Clear all timers.",
        ui_category="Timers",
        ui_description="Remove every active countdown timer and stopwatch.",
    )
)
