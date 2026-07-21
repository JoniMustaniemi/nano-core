from __future__ import annotations

from typing import Any

from app.assistant.response_source import ResponseSource
from app.assistant.tool_executor import ToolExecutor


class DirectToolHandler:
    """
    Run tools that are selected deterministically without planner negotiation.
    """

    def __init__(self, *, tool_executor: ToolExecutor) -> None:
        """
        Initialize the DirectToolHandler instance.

        Args:
            tool_executor: Tool executor value.
        """
        self.tool_executor = tool_executor

    def run(
        self,
        *,
        client: Any,
        conversation_id: str,
        user_message: str,
        tool_name: str,
        args: dict[str, Any] | None = None,
    ) -> ResponseSource:
        """
        Execute a direct tool request and return a structured response source.

        Args:
            client: LLM client retained for API compatibility.
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.
            tool_name: Registered tool name.
            args: Tool argument dictionary.

        Returns:
            Tool result response source.
        """
        _ = client
        return self.tool_executor.run(
            user_message=user_message,
            conversation_id=conversation_id,
            tool_name=tool_name,
            args=args,
        )
