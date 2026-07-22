from __future__ import annotations

from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.response_source import (
  ResponseSource,
  answer_source,
  confirmation_source,
)
from app.assistant.rules.messages import is_confirmation_message, is_rejection_message
from app.runtime.activity import activity
from app.tools.self_update_service import SelfUpdateService


class SelfUpdateInteractionHandler:
  """Handle confirmed git pull for self-update."""

  def start(self, *, conversation_id: str, message: str) -> ResponseSource:
    activity.working(
      title="Nano is preparing confirmation.",
      detail="Preparing confirmation for pulling latest changes.",
      source="assistant.flows.self_update",
    )
    pending_interactions.set(
      conversation_id=conversation_id,
      kind="self_update_confirmation",
      payload={"request": message},
    )
    activity.standby(
      title="Nano needs confirmation.",
      detail="Awaiting confirmation before pulling updates.",
      source="assistant.flows.self_update",
    )
    return confirmation_source(
      user_message=message,
      facts='User requested: "pull latest changes and restart"',
      conversation_id=conversation_id,
    )

  def handle_pending(
    self,
    *,
    pending: PendingInteraction,
    message: str,
    conversation_id: str,
    user_message: str,
  ) -> ResponseSource | None:
    if pending.kind != "self_update_confirmation":
      return None

    if is_rejection_message(message):
      pending_interactions.clear(conversation_id)
      activity.standby(
        title="Nano cancelled the update.",
        detail="The local checkout was left unchanged.",
        source="assistant.flows.self_update",
      )
      return answer_source(
        user_message=user_message,
        facts="Update cancelled. Your checkout was not changed.",
        conversation_id=conversation_id,
      )

    if not is_confirmation_message(message):
      return None

    pending_interactions.clear(conversation_id)
    result = SelfUpdateService().run()
    if not result.ok:
      return answer_source(
        user_message=user_message,
        facts=result.error or "Update failed.",
        conversation_id=conversation_id,
      )

    files = ", ".join(result.changed_files or []) or "none"
    reload_note = (
      "Uvicorn should reload app/ changes automatically."
      if result.reload_expected
      else "No app/ files changed; a manual restart may be needed for other files."
    )
    return answer_source(
      user_message=user_message,
      facts=f"Pulled latest changes. Updated files: {files}. {reload_note}",
      conversation_id=conversation_id,
    )
