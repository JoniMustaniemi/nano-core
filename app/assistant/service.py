from collections.abc import Mapping

from app.assistant.agent import AgentService
from app.assistant.prompts import SYSTEM_PROMPT
from app.assistant.router import get_llm_client
from app.config import get_settings
from app.llm.schemas import ChatResponse
from app.memory import repository
from app.runtime.activity import activity


class AssistantService:
    def respond(self, message: str, mode: str = "agent") -> ChatResponse:
        if mode == "chat":
            return ChatResponse(content=self._chat(message))
        return ChatResponse(content=AgentService().respond(message))

    def _chat(self, message: str) -> str:
        settings = get_settings()
        conversation_id = "default"
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
