from __future__ import annotations

import json
from typing import Any

from app.assistant.response_source import ResponseSource, tool_error_source, tool_result_source
from app.assistant.tool_runner import ToolRunner
from app.runtime.activity import activity


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
        activity.working(
            title=f"Nano is running {tool_name}.",
            detail="Executing the requested tool.",
            source="assistant.tool_executor",
        )
        activity.log(
            title=f"Nano called {tool_name}.",
            detail=json.dumps(tool_args, ensure_ascii=False),
            source="assistant.tool_executor",
        )
        self.tool_runner.announce_call(tool_name)
        result = self.tool_runner.execute(tool_name, tool_args)
        activity.log(
            title=f"Tool {tool_name} returned.",
            detail=result.content,
            source="assistant.tool_executor",
        )
        activity.standby(
            title="Nano finished the task.",
            detail=f"{tool_name} completed.",
            source="assistant.tool_executor",
        )
        if result.ok:
            return tool_result_source(
                user_message=user_message,
                facts=result.content,
                tool_name=tool_name,
                conversation_id=conversation_id,
            )
        return tool_error_source(
            user_message=user_message,
            facts=result.content,
            tool_name=tool_name,
            conversation_id=conversation_id,
        )
