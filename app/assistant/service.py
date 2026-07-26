from __future__ import annotations

from typing import Literal

from app.assistant.orchestrator import AgentOrchestrator
from app.llm.schemas import ChatResponse
from app.runtime.activity import activity
from app.runtime.status_copy import STANDBY_DETAIL_WAITING, choose_wake_ack_response
from app.runtime.user_activity import user_activity


class AssistantService:
    def __init__(self, *, orchestrator: AgentOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or AgentOrchestrator()

    def respond(self, message: str, mode: Literal["chat", "agent"] = "agent") -> ChatResponse:
        conversation_id = "chat-default" if mode == "chat" else "default"
        content, speak = self.orchestrator.respond(
            message,
            conversation_id=conversation_id,
            mode=mode,
        )
        return ChatResponse(content=content, speak=speak)

    def wake_response(self) -> ChatResponse:
        user_activity.touch()
        content = choose_wake_ack_response()
        activity.standby(
            title=content,
            detail=STANDBY_DETAIL_WAITING,
            source="assistant.wake",
        )
        return ChatResponse(content=content)
