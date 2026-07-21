from __future__ import annotations

from typing import Any

from app.assistant.agent_rules import is_pull_request_request
from app.assistant.response_source import ResponseSource
from app.assistant.tool_executor import ToolExecutor


class PullRequestHandler:
    """
    Chat adapter for user-activated pull request creation.
    """

    def __init__(self, *, tool_executor: ToolExecutor) -> None:
        """
        Initialize the pull request handler.

        Args:
            tool_executor: Executor used to run pull request tools.
        """
        self.tool_executor = tool_executor

    def handle_direct_request(
        self,
        *,
        client: Any,
        message: str,
        conversation_id: str,
    ) -> ResponseSource | None:
        """
        Handle a direct pull request request.

        Args:
            client: LLM client retained for API compatibility.
            message: User message or prompt text.
            conversation_id: Conversation identifier.

        Returns:
            Response source when handled; otherwise None.
        """
        _ = client
        if not is_pull_request_request(message):
            return None

        return self.tool_executor.run(
            user_message=message,
            conversation_id=conversation_id,
            tool_name="create_pull_request",
            args={},
        )
