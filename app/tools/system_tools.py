from __future__ import annotations

from typing import Any

from app.system.specs import format_system_analysis_report
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _analyze_system(args: dict[str, Any]) -> str:
    del args
    return format_system_analysis_report()


register_tool(
    ToolSpec(
        name="analyze_system",
        description="Summarize my models, memory headroom, and context limits.",
        args_schema={},
        handler=_analyze_system,
        announcement="Analyzing system specs.",
        keywords=(
            "system analysis",
            "analyze system",
            "analyze my system",
            "run a system analysis",
            "can you run a system analysis",
            "system specs",
            "check system specs",
            "check my system",
            "what are my system specs",
            "hardware specs",
            "memory available",
            "how much memory",
        ),
        ui_label="System analysis",
        ui_message="Analyze my system specs.",
        ui_category="System",
        ui_description="My models, memory, and context limits.",
    )
)
