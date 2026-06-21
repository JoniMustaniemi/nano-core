from __future__ import annotations

from typing import Any

from app.assistant.agent_rules import tool_announcement
from app.assistant.agent_types import ToolResult
from app.runtime.activity import activity
from app.tools import get_tool, list_tools
from app.voice.service import GladosVoiceService, VoiceUnavailableError


class ToolRunner:
    def execute(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        tool = get_tool(tool_name)
        if tool is None:
            available = ", ".join(tool_spec.name for tool_spec in list_tools())
            error_message = f"Unknown tool: {tool_name}. Available tools: {available}"
            self.report_error(
                title=f"Nano could not call {tool_name}.",
                detail=error_message,
                spoken_message="I hit a tool error while trying to complete the task.",
            )
            return ToolResult(tool=tool_name, content=error_message)

        try:
            return ToolResult(tool=tool_name, content=tool.handler(args))
        except Exception as exc:
            error_message = f"Error while running {tool_name}: {exc}"
            self.report_error(
                title=f"Nano hit an error in {tool_name}.",
                detail=error_message,
                spoken_message="I hit an error while trying to complete the task.",
            )
            return ToolResult(tool=tool_name, content=error_message)

    def announce_call(self, tool_name: str) -> None:
        self._announce(tool_announcement(tool_name))

    def report_error(self, *, title: str, detail: str, spoken_message: str) -> None:
        activity.error(title=title, detail=detail, source="assistant.agent")
        self._announce(spoken_message)

    def _announce(self, message: str) -> None:
        try:
            GladosVoiceService().announce(message)
        except VoiceUnavailableError:
            return
