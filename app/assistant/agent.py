from __future__ import annotations

from app.assistant.orchestrator import AgentOrchestrator


class AgentService:
    def __init__(self, *, orchestrator: AgentOrchestrator | None = None) -> None:
        """
        Initialize the AgentService instance.

        Args:
            orchestrator: Unified response orchestrator.

        Returns:
            None.
        """
        self.orchestrator = orchestrator or AgentOrchestrator()

    def respond(self, message: str, conversation_id: str = "default") -> str:
        """
        Respond to the requested operation.

        Args:
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history and pending state.

        Returns:
            Generated or formatted string value.
        """
        return self.orchestrator.respond(message, conversation_id=conversation_id)
