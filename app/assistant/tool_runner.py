from __future__ import annotations

import json
from typing import Any

from app.assistant.agent_types import ToolResult
from app.runtime.activity import activity
from app.runtime.status_copy import (
    could_not_call_tool_title,
    failed_tool_title,
    running_tool_title,
    tool_error_title,
)
from app.tools import get_tool, list_tools
from app.tools.errors import ToolError
from app.voice.service import GladosVoiceService, VoiceUnavailableError

_STRUCTURED_RESULT_TOOLS = frozenset(
    {"propose_self_changes", "create_pull_request", "apply_updates_and_restart"}
)
_STRUCTURED_FAILURE_TITLES: dict[str, str] = {
    "propose_self_changes": failed_tool_title("propose_self_changes"),
    "create_pull_request": failed_tool_title("create_pull_request"),
}
_STRUCTURED_FAILURE_SPOKEN: dict[str, str] = {
    "propose_self_changes": "I could not complete the self-improvement.",
    "create_pull_request": "I could not complete the pull request.",
    "apply_updates_and_restart": "I could not pull the latest changes.",
}


class ToolRunner:
    def execute(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """
        Execute the requested operation.

        Args:
            tool_name: Registered tool name.
            args: Tool argument dictionary.

        Returns:
            ToolResult result.
        """
        tool = get_tool(tool_name)
        if tool is None:
            available = ", ".join(tool_spec.name for tool_spec in list_tools())
            error_message = f"Unknown tool: {tool_name}. Available tools: {available}"
            self.report_error(
                title=could_not_call_tool_title(tool_name),
                detail=error_message,
                spoken_message="I hit a tool error while trying to complete the task.",
            )
            return ToolResult(
                tool=tool_name,
                content=json.dumps({"ok": False, "error": error_message}),
                ok=False,
            )

        try:
            content = tool.handler(args)
            structured = self._parse_structured_result(content)
            if (
                tool_name in _STRUCTURED_RESULT_TOOLS
                and structured is not None
                and structured.get("ok") is False
            ):
                error_message = str(structured.get("error", "")).strip()
                self.report_error(
                    title=_STRUCTURED_FAILURE_TITLES.get(
                        tool_name,
                        tool_error_title(tool_name),
                    ),
                    detail=error_message or "The tool reported a failure.",
                    spoken_message=_STRUCTURED_FAILURE_SPOKEN.get(
                        tool_name,
                        "I hit an error while trying to complete the task.",
                    ),
                )
                return ToolResult(
                    tool=tool_name,
                    content=content if isinstance(content, str) else json.dumps(structured),
                    ok=False,
                )
            return ToolResult(tool=tool_name, content=content, ok=True)
        except ToolError as exc:
            error_message = str(exc)
            self.report_error(
                title=tool_error_title(tool_name),
                detail=error_message,
                spoken_message="I hit an error while trying to complete the task.",
            )
            return ToolResult(
                tool=tool_name,
                content=json.dumps({"ok": False, "error": error_message}),
                ok=False,
            )
        except Exception as exc:
            error_message = f"Error while running {tool_name}: {exc}"
            self.report_error(
                title=tool_error_title(tool_name),
                detail=error_message,
                spoken_message="I hit an error while trying to complete the task.",
            )
            return ToolResult(
                tool=tool_name,
                content=json.dumps({"ok": False, "error": error_message}),
                ok=False,
            )

    def announce_call(self, tool_name: str) -> None:
        """
        Announce call.

        Args:
            tool_name: Registered tool name.

        Returns:
            None.
        """
        self.announce_message(running_tool_title(tool_name))

    def announce_message(self, message: str) -> None:
        """
        Announce a user-facing status message.

        Args:
            message: Message suitable for voice announcement.

        Returns:
            None.
        """
        spoken = message.strip().rstrip(".")
        if spoken:
            self._announce(spoken)

    def report_error(self, *, title: str, detail: str, spoken_message: str) -> None:
        """
        Report error.

        Args:
            title: Short error title to report.
            detail: Detailed error text to report.
            spoken_message: Message suitable for voice announcement.

        Returns:
            None.
        """
        activity.error(title=title, detail=detail, source="assistant.agent")
        self._announce(spoken_message)

    def _announce(self, message: str) -> None:
        """
        Announce the requested operation.

        Args:
            message: User message or prompt text.

        Returns:
            None.
        """
        try:
            GladosVoiceService().announce(message)
        except VoiceUnavailableError:
            return

    def _parse_structured_result(self, content: Any) -> dict[str, Any] | None:
        if isinstance(content, dict):
            payload = content
        elif isinstance(content, str) and content.strip().startswith("{"):
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                return None
        else:
            return None
        return payload if isinstance(payload, dict) and "ok" in payload else None
