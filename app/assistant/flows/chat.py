from __future__ import annotations

from typing import Any

from app.assistant.prompts import AGENT_SYSTEM_PROMPT, SYSTEM_PROMPT
from app.assistant.response_guard import enforce_user_facing_answer
from app.llm.protocol import LLMClient
from app.memory import repository
from app.runtime.activity import activity
from app.tools import FLOW_OWNED_TOOLS, render_tool_prompt


class AgentChatFlow:
    """
    Build agent chat prompts and plain chat fallbacks.
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

    def fallback_to_chat(
        self,
        *,
        client: LLMClient,
        message: str,
        conversation_id: str,
        history: list[Any],
    ) -> str:
        """
        Answer directly with chat mode when planning is not needed or failed.

        Args:
            client: LLM client used to generate responses.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.
            history: Chat history records.

        Returns:
            User-facing assistant answer.
        """
        activity.working(
            title="Nano is answering.",
            detail="Using plain chat mode with the local model.",
            source="assistant.flows.chat",
        )
        fallback_messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for entry in history:
            fallback_messages.append({"role": entry.role, "content": entry.content})
        if not history or history[-1].role != "user" or history[-1].content != message:
            fallback_messages.append({"role": "user", "content": message})

        content = client.complete(messages=fallback_messages)
        content = enforce_user_facing_answer(client, message, content)
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
        )
        activity.standby(
            title="Nano answered without tools.",
            detail="The local model could not follow agent JSON, so Nano used plain chat mode.",
            source="assistant.flows.chat",
        )
        return content

    def system_prompt(self) -> str:
        """
        Build the agent system prompt with available tools.

        Returns:
            System prompt text.
        """
        return AGENT_SYSTEM_PROMPT + "\n\n" + render_tool_prompt(exclude=FLOW_OWNED_TOOLS)
