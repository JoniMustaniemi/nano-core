from __future__ import annotations

import json
from typing import Any

from app.assistant.response_source import ResponseSource, tool_error_source, tool_result_source
from app.assistant.tool_runner import ToolRunner
from app.runtime.activity import activity
from app.runtime.status_copy import failed_tool_title, ran_tool_title

_SILENT_TOOL_NAMES = frozenset({"rename_timer", "rename_stopwatch"})


class ToolExecutor:
    """
    Execute tools and return structured response sources.
    """

    def __init__(self, *, tool_runner: ToolRunner | None = None) -> None:
        """
        Initialize the tool executor.

        Args:
            tool_runner: Tool runner used to execute registered tools.
        """
        self.tool_runner = tool_runner or ToolRunner()

    def run(
        self,
        *,
        user_message: str,
        conversation_id: str,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> ResponseSource:
        """
        Execute a tool and return a structured response source.

        Args:
            user_message: Original user message.
            conversation_id: Conversation identifier.
            tool_name: Registered tool name.
            args: Tool argument dictionary.

        Returns:
            Tool result or error response source.
        """
        tool_args = args or {}
        result = self.tool_runner.execute(tool_name, tool_args)
        if result.ok:
            activity.log(
                title=ran_tool_title(tool_name),
                detail="Done.",
                source="assistant.tool_executor",
            )
        else:
            activity.log(
                title=failed_tool_title(tool_name),
                detail=_tool_failure_detail(result),
                source="assistant.tool_executor",
            )
        silent = (
            tool_name in _SILENT_TOOL_NAMES
            or (tool_name == "cancel_timers" and tool_args.get("timer_id") not in (None, ""))
            or (tool_name == "stop_stopwatches" and tool_args.get("stopwatch_id") not in (None, ""))
        )
        if result.ok:
            return tool_result_source(
                user_message=user_message,
                facts="" if silent else result.content,
                tool_name=tool_name,
                conversation_id=conversation_id,
                persist=not silent,
                speak=not silent,
            )
        error_facts = _silent_tool_error_facts(result.content) if silent else result.content
        return tool_error_source(
            user_message=user_message,
            facts=error_facts,
            tool_name=tool_name,
            conversation_id=conversation_id,
            persist=not silent,
            speak=not silent,
        )


def _silent_tool_error_facts(content: str) -> str:
    if content.strip().startswith("{"):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return content
        if isinstance(payload, dict):
            error = str(payload.get("error", "")).strip()
            if error:
                return error
    return content


def _tool_failure_detail(result: Any) -> str:
    if isinstance(result.content, str) and result.content.strip().startswith("{"):
        try:
            payload = json.loads(result.content)
        except json.JSONDecodeError:
            return "The tool reported a failure."
        if isinstance(payload, dict):
            error = str(payload.get("error", "")).strip()
            if error:
                return error
    return "The tool reported a failure."
