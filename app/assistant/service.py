from __future__ import annotations

from app.assistant.agent import AgentService
from app.assistant.agent_rules import is_capability_question, is_identity_question
from app.assistant.answer_executor import AnswerExecutor
from app.assistant.response_composer import ResponseComposer
from app.assistant.response_pipeline import finalize_response
from app.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.schemas import ChatResponse
from app.memory import repository
from app.runtime.activity import activity
from app.runtime.status_copy import (
    RECEIVED_DETAIL,
    RECEIVED_TITLE,
    STANDBY_DETAIL_WAITING,
    THINKING_DETAIL,
    THINKING_TITLE,
    choose_wake_ack_response,
)
from app.runtime.user_activity import user_activity


class AssistantService:
    def __init__(
        self,
        *,
        composer: ResponseComposer | None = None,
        answer_executor: AnswerExecutor | None = None,
    ) -> None:
        """
        Initialize the assistant service.

        Args:
            composer: Response composer used for chat and wake replies.
            answer_executor: Answer executor used to draft chat replies.
        """
        self.composer = composer or ResponseComposer()
        self.answer_executor = answer_executor or AnswerExecutor()

    def respond(self, message: str, mode: str = "agent") -> ChatResponse:
        """
        Respond to the requested operation.

        Args:
            message: User message or prompt text.
            mode: Assistant response mode to use.

        Returns:
            ChatResponse result.
        """
        if mode == "chat":
            content, speak = self._chat_with_voice(message, conversation_id="chat-default")
            return ChatResponse(content=content, speak=speak)
        content, speak = AgentService().respond_with_voice(message, conversation_id="agent-default")
        return ChatResponse(content=content, speak=speak)

    def wake_response(self) -> ChatResponse:
        """
        Return the wake response for response.

        Returns:
            ChatResponse result.
        """
        user_activity.touch()
        content = choose_wake_ack_response()
        activity.standby(
            title=content,
            detail=STANDBY_DETAIL_WAITING,
            source="assistant.wake",
        )
        return ChatResponse(content=content)

    def _chat_with_voice(self, message: str, conversation_id: str) -> tuple[str, bool]:
        return self._chat(message, conversation_id=conversation_id)

    def _chat(self, message: str, conversation_id: str) -> tuple[str, bool]:
        """
        Handle chat input and return a response.

        Args:
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history and pending state.

        Returns:
            Generated or formatted string value.
        """
        settings = get_settings()
        user_activity.touch()
        activity.working(
            title=RECEIVED_TITLE,
            detail=RECEIVED_DETAIL,
            source="assistant.chat",
        )
        repository.add_chat_message(conversation_id=conversation_id, role="user", content=message)
        history = repository.list_chat_messages(
            conversation_id=conversation_id,
            limit=settings.chat_history_limit,
        )
        client = get_llm_client()
        activity.working(
            title=THINKING_TITLE,
            detail=THINKING_DETAIL,
            source="assistant.chat",
        )
        if is_capability_question(message):
            source = self.answer_executor.draft_capabilities(
                client=client,
                message=message,
                conversation_id=conversation_id,
            )
        elif is_identity_question(message):
            source = self.answer_executor.draft_identity(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )
        else:
            source = self.answer_executor.draft(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )
        return finalize_response(
            client,
            source,
            composer=self.composer,
            standby_source="assistant.chat",
        )
