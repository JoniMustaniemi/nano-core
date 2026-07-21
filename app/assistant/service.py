from collections.abc import Mapping
from typing import Any

from app.assistant.agent import AgentService
from app.assistant.answer_executor import AnswerExecutor
from app.assistant.llm_factory import get_llm_client
from app.assistant.response_composer import ResponseComposer
from app.assistant.response_guard import (
    enforce_user_facing_answer,
    looks_like_self_description_instead_of_answer,
)
from app.assistant.response_source import answer_source
from app.config import get_settings
from app.llm.schemas import ChatResponse
from app.memory import repository
from app.runtime.activity import activity


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
            return ChatResponse(content=self._chat(message, conversation_id="chat-default"))
        return ChatResponse(
            content=AgentService().respond(message, conversation_id="agent-default")
        )

    def wake_response(self) -> ChatResponse:
        """
        Return the wake response for response.

        Returns:
            ChatResponse result.
        """
        client = get_llm_client()
        source = self.answer_executor.draft_wake(client=client)
        content = self.composer.compose(client, source)
        return ChatResponse(content=content)

    def _chat(self, message: str, conversation_id: str) -> str:
        """
        Handle chat input and return a response.

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
        client = get_llm_client()
        activity.working(
            title="Nano is thinking.",
            detail="Loading memory and talking to the local model.",
            source="assistant.chat",
        )
        source = self.answer_executor.draft(
            client=client,
            message=message,
            conversation_id=conversation_id,
            history=self._history_with_notes(
                history=history,
                user_message=message,
                note_limit=settings.note_context_limit,
            ),
        )
        draft = source.facts
        if looks_like_self_description_instead_of_answer(message, draft):
            from app.assistant.prompts import ACTUAL_ANSWER_REWRITE_SYSTEM_PROMPT

            retry_messages: list[Mapping[str, str]] = [
                {"role": "system", "content": ACTUAL_ANSWER_REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ]
            draft = client.complete(messages=retry_messages)
            source = answer_source(
                user_message=message,
                facts=draft,
                conversation_id=conversation_id,
            )
        content = self.composer.compose(client, source)
        content = enforce_user_facing_answer(client, message, content)
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
        )
        activity.standby(
            title="Nano is back in standby.",
            detail="The chat response is ready.",
            source="assistant.chat",
        )
        return content

    def _history_with_notes(
        self,
        *,
        history: list[Any],
        user_message: str,
        note_limit: int,
    ) -> list[Any]:
        """
        Build chat history with note context for answer drafting.

        Args:
            history: Stored chat history records.
            user_message: Current user message.
            note_limit: Maximum notes to include.

        Returns:
            History-like records including note context when available.
        """
        notes = repository.list_notes(limit=note_limit)
        if not notes:
            return history

        note_lines = "\n".join(f"- {note.name}: {note.content}" for note in notes)
        note_context = SimpleHistoryEntry(
            role="system",
            content=(
                "Relevant notes from Nano's memory:\n"
                f"{note_lines}\n"
                "Use them as background context when helpful."
            ),
        )
        return [*history, note_context]


class SimpleHistoryEntry:
    """Minimal history entry for injecting note context into answer drafting."""

    def __init__(self, *, role: str, content: str) -> None:
        self.role = role
        self.content = content
