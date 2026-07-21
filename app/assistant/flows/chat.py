from __future__ import annotations

from typing import Any

from app.assistant.prompts import AGENT_SYSTEM_PROMPT
from app.tools import FLOW_OWNED_TOOLS, render_tool_prompt


class AgentChatFlow:
    """
    Build agent chat prompts for the planner.
    """

    def build_agent_messages(
        self,
        *,
        history: list[Any],
        message: str,
    ) -> list[dict[str, str]]:
        """
        Build planner messages from chat history.

        Args:
            history: Chat history records.
            message: User message or prompt text.

        Returns:
            Message dictionaries for the agent planner.
        """
        messages: list[dict[str, str]] = [{"role": "system", "content": self.system_prompt()}]
        for entry in history:
            messages.append({"role": entry.role, "content": entry.content})
        if not history or history[-1].role != "user" or history[-1].content != message:
            messages.append({"role": "user", "content": message})
        return messages

    def system_prompt(self) -> str:
        """
        Build the agent system prompt with available tools.

        Returns:
            System prompt text.
        """
        return AGENT_SYSTEM_PROMPT + "\n\n" + render_tool_prompt(exclude=FLOW_OWNED_TOOLS)
