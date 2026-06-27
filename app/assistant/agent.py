from __future__ import annotations

from typing import Any

from app.assistant.agent_rules import (
    is_health_check_request,
    needs_wipe_confirmation,
    should_answer_without_tools,
)
from app.assistant.flows.chat import AgentChatFlow
from app.assistant.flows.direct_tool import DirectToolHandler
from app.assistant.flows.note import NoteInteractionHandler
from app.assistant.flows.planner import AgentPlanner
from app.assistant.flows.timer import TimerInteractionHandler
from app.assistant.flows.wipe import WipeInteractionHandler
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.result_summarizer import ToolResultSummarizer
from app.assistant.router import get_llm_client
from app.assistant.tool_runner import ToolRunner
from app.config import get_settings
from app.memory import repository


class AgentService:
    def __init__(
        self,
        *,
        tool_runner: ToolRunner | None = None,
        chat_flow: AgentChatFlow | None = None,
        direct_tool_handler: DirectToolHandler | None = None,
        note_handler: NoteInteractionHandler | None = None,
        planner: AgentPlanner | None = None,
        summarizer: ToolResultSummarizer | None = None,
        timer_handler: TimerInteractionHandler | None = None,
        wipe_handler: WipeInteractionHandler | None = None,
    ) -> None:
        """
        Initialize the AgentService instance.

        Args:
            tool_runner: Tool runner value.
            chat_flow: Chat and prompt flow value.
            direct_tool_handler: Direct tool handler value.
            note_handler: Note interaction handler value.
            planner: Agent planner value.
            summarizer: Summarizer value.
            timer_handler: Timer interaction handler value.
            wipe_handler: Wipe interaction handler value.

        Returns:
            None.
        """
        self.tool_runner = tool_runner or ToolRunner()
        self.summarizer = summarizer or ToolResultSummarizer()
        self.chat_flow = chat_flow or AgentChatFlow()
        self.direct_tool_handler = direct_tool_handler or DirectToolHandler(
            tool_runner=self.tool_runner,
            summarizer=self.summarizer,
        )
        self.note_handler = note_handler or NoteInteractionHandler()
        self.timer_handler = timer_handler or TimerInteractionHandler(
            tool_runner=self.tool_runner,
            direct_tool_handler=self.direct_tool_handler,
        )
        self.wipe_handler = wipe_handler or WipeInteractionHandler()
        self.planner = planner or AgentPlanner(
            tool_runner=self.tool_runner,
            chat_flow=self.chat_flow,
        )

    def respond(self, message: str, conversation_id: str = "default") -> str:
        """
        Respond to the requested operation.

        Args:
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history and pending state.

        Returns:
            Generated or formatted string value.
        """
        settings = get_settings()
        repository.add_chat_message(conversation_id=conversation_id, role="user", content=message)

        history = repository.list_chat_messages(
            conversation_id=conversation_id,
            limit=settings.chat_history_limit,
        )
        messages = self.chat_flow.build_agent_messages(history=history, message=message)
        client = get_llm_client()
        direct_response = self._handle_direct_request(
            client=client,
            conversation_id=conversation_id,
            message=message,
            history=history,
        )
        if direct_response is not None:
            return direct_response

        return self.planner.run(
            client=client,
            conversation_id=conversation_id,
            message=message,
            history=history,
            messages=messages,
        )

    def _handle_direct_request(
        self,
        *,
        client: Any,
        conversation_id: str,
        message: str,
        history: list[Any],
    ) -> str | None:
        timer_response = self.timer_handler.handle_direct_request(
            client=client,
            message=message,
            conversation_id=conversation_id,
        )
        if timer_response is not None:
            return timer_response

        pending_response = self._handle_pending_interaction(
            pending=pending_interactions.get(conversation_id),
            message=message,
            conversation_id=conversation_id,
        )
        if pending_response is not None:
            return pending_response

        if needs_wipe_confirmation(message):
            return self.wipe_handler.start(
                client=client,
                conversation_id=conversation_id,
                message=message,
            )

        note_response = self.note_handler.handle_direct_request(
            message=message,
            conversation_id=conversation_id,
        )
        if note_response is not None:
            return note_response

        if is_health_check_request(message):
            return self.direct_tool_handler.run(
                client=client,
                conversation_id=conversation_id,
                user_message=message,
                tool_name="check_health",
                args={},
                summarize_result=True,
            )

        if should_answer_without_tools(message):
            return self.chat_flow.fallback_to_chat(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )

        return None

    def _handle_pending_interaction(
        self,
        *,
        pending: PendingInteraction | None,
        message: str,
        conversation_id: str,
    ) -> str | None:
        if pending is None:
            return None

        for handler in (
            self.timer_handler,
            self.note_handler,
            self.wipe_handler,
        ):
            response = handler.handle_pending(
                pending=pending,
                message=message,
                conversation_id=conversation_id,
            )
            if response is not None:
                return response

        pending_interactions.clear(conversation_id)
        return None
