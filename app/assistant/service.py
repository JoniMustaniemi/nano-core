from collections.abc import Mapping

from app.assistant.agent import AgentService
from app.assistant.prompts import SYSTEM_PROMPT
from app.assistant.response_guard import (
    enforce_first_person_self_reference,
    enforce_user_facing_answer,
    looks_like_self_description_instead_of_answer,
)
from app.assistant.router import get_llm_client
from app.config import get_settings
from app.llm.schemas import ChatResponse
from app.memory import repository
from app.runtime.activity import activity


class AssistantService:
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
        messages: list[Mapping[str, str]] = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + " You just heard your wake phrase. "
                    + "Reply with one short sentence that confirms you are listening "
                    + "and invites the user's command. "
                    + "Stay in Nano's personality. "
                    + "Do not greet warmly. "
                    + "Do not mention capabilities, tools, JSON, or internal systems. "
                    + "Keep it brief and natural to speak aloud."
                ),
            },
            {
                "role": "user",
                "content": "The user said your wake phrase and is waiting for acknowledgment.",
            },
        ]
        content = client.complete(messages=messages).strip()
        content = enforce_first_person_self_reference(client, content)
        if not content:
            content = "I am listening. Proceed."
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
        messages = self._build_messages(
            user_message=message,
            conversation_id=conversation_id,
            history_limit=settings.chat_history_limit,
            note_limit=settings.note_context_limit,
        )
        client = get_llm_client()
        activity.working(
            title="Nano is thinking.",
            detail="Loading memory and talking to the local model.",
            source="assistant.chat",
        )
        content = client.complete(messages=messages)
        if looks_like_self_description_instead_of_answer(message, content):
            retry_messages: list[Mapping[str, str]] = [
                {
                    "role": "system",
                    "content": (
                        SYSTEM_PROMPT
                        + " The last answer was wrong because it described your identity "
                        "or capabilities instead of answering the user's question. Answer "
                        "the user's last message directly. If you cannot determine the answer, "
                        "give a concise personality-driven answer that makes the missing "
                        "evidence clear."
                    ),
                },
                {"role": "user", "content": message},
            ]
            content = client.complete(messages=retry_messages)
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

    def _build_messages(
        self,
        *,
        user_message: str,
        conversation_id: str,
        history_limit: int,
        note_limit: int,
    ) -> list[Mapping[str, str]]:
        """
        Build messages.

        Args:
            user_message: User message value.
            conversation_id: Conversation identifier used to scope history and pending state.
            history_limit: History limit value.
            note_limit: Note limit value.

        Returns:
            List of matching records or values.
        """
        messages: list[Mapping[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        notes = repository.list_notes(limit=note_limit)
        if notes:
            note_lines = "\n".join(f"- {note.content}" for note in notes)
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Relevant notes from Nano's memory:\n"
                        f"{note_lines}\n"
                        "Use them as background context when helpful."
                    ),
                }
            )

        history = repository.list_chat_messages(
            conversation_id=conversation_id,
            limit=history_limit,
        )
        for entry in history:
            messages.append({"role": entry.role, "content": entry.content})

        if not history or history[-1].role != "user" or history[-1].content != user_message:
            messages.append({"role": "user", "content": user_message})

        return messages
