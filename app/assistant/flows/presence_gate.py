from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.assistant.pending import pending_interactions
from app.assistant.response_source import ResponseSource, answer_source
from app.config import get_settings
from app.llm.factory import get_llm_client
from app.memory.internal_note_service import internal_note_service
from app.proactive.registry import delivery_registry
from app.proactive.store import proactive_store
from app.proactive.types import ProactiveOffer
from app.runtime.activity import activity
from app.runtime.status_copy import (
  PRESENCE_FOLLOW_UP_DETAIL,
  PRESENCE_TIMEOUT_DETAIL,
  PRESENCE_TIMEOUT_TITLE,
  PRESENCE_TITLE,
  STANDBY_DETAIL_PRESENCE,
)
from app.voice.service import GladosVoiceService, VoiceUnavailableError


class PresenceGateHandler:
  """Reusable presence check before delivering proactive offers."""

  def start(
    self,
    offer: ProactiveOffer,
    *,
    internal_note_id: int | None = None,
    conversation_id: str | None = None,
    follow_up: bool = False,
  ) -> None:
    settings = get_settings()
    conversation = conversation_id or settings.proactive_conversation_id
    proactive_store.set_offer(offer, internal_note_id=internal_note_id)
    proactive_store.start_presence()
    pending_interactions.set(
      conversation_id=conversation,
      kind="presence_check",
      payload={
        "offer_kind": offer.kind,
        "internal_note_id": internal_note_id,
        "presence_started_at": datetime.now(UTC).isoformat(),
        "follow_up": follow_up,
      },
    )
    detail = PRESENCE_FOLLOW_UP_DETAIL if follow_up else STANDBY_DETAIL_PRESENCE
    activity.standby(
      title=PRESENCE_TITLE,
      detail=detail,
      source="proactive.presence_gate",
    )
    self._announce(PRESENCE_TITLE)

  def handle_pending(
    self,
    *,
    message: str,
    conversation_id: str,
    client: Any | None = None,
  ) -> ResponseSource | None:
    from app.assistant.rules.messages import is_presence_confirmation, is_rejection_message

    pending = pending_interactions.get(conversation_id)
    if pending is None or pending.kind != "presence_check":
      return None

    offer = proactive_store.get_offer()
    if offer is None:
      pending_interactions.clear(conversation_id)
      proactive_store.clear_offer()
      return None

    internal_note_id = pending.payload.get("internal_note_id")
    parsed_note_id = int(internal_note_id) if internal_note_id is not None else None

    if is_rejection_message(message):
      pending_interactions.clear(conversation_id)
      proactive_store.clear_offer()
      if parsed_note_id is not None:
        internal_note_service.record_deferred_offer(
          offer,
          reason="user_rejected",
          note_id=parsed_note_id,
        )
      else:
        internal_note_service.record_deferred_offer(offer, reason="user_rejected")
      return answer_source(
        user_message=message,
        facts="Understood. I will ask again later.",
        conversation_id=conversation_id,
      )

    if not is_presence_confirmation(message):
      return answer_source(
        user_message=message,
        facts="Reply yes if you are there, or no if not.",
        conversation_id=conversation_id,
      )

    pending_interactions.clear(conversation_id)
    proactive_store.clear_presence()
    llm_client = client or get_llm_client()
    source = delivery_registry.deliver(
      offer=offer,
      client=llm_client,
      conversation_id=conversation_id,
    )
    if parsed_note_id is not None:
      internal_note_service.mark_delivered(parsed_note_id)
    goal = str(offer.payload.get("goal", "")).strip()
    if goal:
      raw_files = offer.payload.get("files", [])
      files = [str(path) for path in raw_files if str(path).strip()] if isinstance(raw_files, list) else []
      proactive_store.set_last_goal(goal, files=files or None)
    proactive_store.clear_offer()
    return source

  def handle_timeout(self) -> None:
    settings = get_settings()
    conversation_id = settings.proactive_conversation_id
    pending = pending_interactions.get(conversation_id)
    if pending is None or pending.kind != "presence_check":
      return

    offer = proactive_store.get_offer()
    if offer is None:
      pending_interactions.clear(conversation_id)
      proactive_store.clear_offer()
      return

    internal_note_id = pending.payload.get("internal_note_id")
    parsed_note_id = int(internal_note_id) if internal_note_id is not None else None

    pending_interactions.clear(conversation_id)
    proactive_store.set_dismissal(PRESENCE_TIMEOUT_TITLE)
    if parsed_note_id is not None:
      internal_note_service.record_deferred_offer(
        offer,
        reason="presence_timeout",
        note_id=parsed_note_id,
      )
    else:
      internal_note_service.record_deferred_offer(offer, reason="presence_timeout")
    proactive_store.clear_offer()

    activity.standby(
      title=PRESENCE_TIMEOUT_TITLE,
      detail=PRESENCE_TIMEOUT_DETAIL,
      source="proactive.presence_gate",
    )
    self._announce(PRESENCE_TIMEOUT_TITLE)

  def _announce(self, message: str) -> None:
    try:
      GladosVoiceService().announce(message)
    except VoiceUnavailableError:
      return


presence_gate = PresenceGateHandler()
