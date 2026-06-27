from __future__ import annotations

from typing import Any, cast

from app.assistant.agent_rules import (
    is_confirmation_message,
    is_rejection_message,
    wipe_confirmation_prompt,
)
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.prompts import WIPE_CONFIRMATION_SYSTEM_PROMPT
from app.assistant.response_guard import enforce_first_person_self_reference
from app.memory import repository
from app.runtime.activity import activity


class WipeInteractionHandler:
    """
    Handle destructive database wipe confirmation flow.
    """

    def start(
        self,
        *,
        client: Any,
        conversation_id: str,
        message: str,
    ) -> str:
        """
        Start a wipe confirmation interaction.

        Args:
            client: LLM client used to generate confirmation wording.
            conversation_id: Conversation identifier used to scope history.
            message: User message or prompt text.

        Returns:
            Confirmation prompt.
        """
        activity.working(
            title="Nano is preparing confirmation.",
            detail="Using the local model to respond to the destructive request.",
            source="assistant.flows.wipe",
        )
        confirmation_prompt = self._build_confirmation_prompt(
            client=client,
            message=message,
        )
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="wipe_confirmation",
            payload={"request": message},
        )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=confirmation_prompt,
        )
        activity.standby(
            title="Nano needs confirmation.",
            detail="Waiting for confirmation before wiping the database.",
            source="assistant.flows.wipe",
        )
        return confirmation_prompt

    def handle_pending(
        self,
        *,
        pending: PendingInteraction,
        message: str,
        conversation_id: str,
    ) -> str | None:
        """
        Continue a pending wipe confirmation interaction.

        Args:
            pending: Pending interaction.
            message: User message or prompt text.
            conversation_id: Conversation identifier used to scope history.

        Returns:
            Wipe response when handled; otherwise None.
        """
        if pending.kind != "wipe_confirmation":
            return None

        if is_rejection_message(message):
            response = "Database wipe cancelled."
            pending_interactions.clear(conversation_id)
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
            activity.standby(
                title="Nano cancelled the wipe.",
                detail="The database was left intact.",
                source="assistant.flows.wipe",
            )
            return response

        if not is_confirmation_message(message):
            response = "Reply yes to confirm the database wipe, or no to cancel."
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
            activity.standby(
                title="Nano still needs confirmation.",
                detail="Waiting for a clear yes or no before wiping the database.",
                source="assistant.flows.wipe",
            )
            return response

        activity.working(
            title="Nano is wiping the database.",
            detail="Deleting stored notes, reminders, and chat history.",
            source="assistant.flows.wipe",
        )
        repository.wipe_database()
        pending_interactions.clear(conversation_id)
        response = "Database wiped."
        activity.standby(
            title="Nano wiped the database.",
            detail="Notes, reminders, and chat history were deleted.",
            source="assistant.flows.wipe",
        )
        return response

    def _build_confirmation_prompt(self, *, client: Any, message: str) -> str:
        """
        Build the user-facing wipe confirmation prompt.

        Args:
            client: LLM client used to generate confirmation wording.
            message: User message or prompt text.

        Returns:
            Confirmation prompt text.
        """
        prompt_messages = [
            {"role": "system", "content": WIPE_CONFIRMATION_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]
        draft = cast(str, client.complete(messages=prompt_messages)).strip()
        draft = enforce_first_person_self_reference(client, draft)
        if not draft:
            return wipe_confirmation_prompt(message)
        cleaned = draft.replace("\n", " ").strip()
        cleaned = cleaned.rstrip(". ")
        return f"{cleaned}. Reply yes to proceed or no to cancel."
