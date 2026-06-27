from __future__ import annotations

import json
from typing import Any

from app.assistant.result_summarizer import ToolResultSummarizer
from app.assistant.tool_runner import ToolRunner
from app.memory import repository
from app.runtime.activity import activity


class DirectToolHandler:
    """
    Run tools that are selected deterministically without planner negotiation.
    """

    def __init__(
        self,
        *,
        tool_runner: ToolRunner,
        summarizer: ToolResultSummarizer,
    ) -> None:
        """
        Initialize the DirectToolHandler instance.

        Args:
            tool_runner: Tool runner value.
            summarizer: Tool result summarizer value.

        Returns:
            None.
        """
        self.tool_runner = tool_runner
        self.summarizer = summarizer

    def run(
        self,
        *,
        client: Any,
        conversation_id: str,
        user_message: str,
        tool_name: str,
        args: dict[str, Any],
        summarize_result: bool = False,
    ) -> str:
        """
        Execute a direct tool request and persist the assistant response.

        Args:
            client: LLM client used for optional result summarization.
            conversation_id: Conversation identifier used to scope history.
            user_message: Original user message.
            tool_name: Registered tool name.
            args: Tool argument dictionary.
            summarize_result: Whether to summarize the raw tool result.

        Returns:
            Tool result or summarized response.
        """
        activity.working(
            title=f"Nano is running {tool_name}.",
            detail="Executing the requested tool.",
            source="assistant.flows.direct_tool",
        )
        activity.log(
            title=f"Nano called {tool_name}.",
            detail=json.dumps(args, ensure_ascii=False),
            source="assistant.flows.direct_tool",
        )
        self.tool_runner.announce_call(tool_name)
        result = self.tool_runner.execute(tool_name, args)
        activity.log(
            title=f"Tool {tool_name} returned.",
            detail=result.content,
            source="assistant.flows.direct_tool",
        )
        content = result.content
        if summarize_result:
            content = self.summarizer.summarize(
                client=client,
                user_message=user_message,
                tool_name=tool_name,
                tool_result=result.content,
            )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
        )
        activity.standby(
            title="Nano finished the task.",
            detail=f"{tool_name} completed.",
            source="assistant.flows.direct_tool",
        )
        return content
