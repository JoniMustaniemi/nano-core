from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.assistant.rules.intents import is_vague_self_improve_goal
from app.config import get_settings
from app.memory import internal_notes
from app.memory.models import InternalNote
from app.proactive.types import ProactiveOffer
from app.runtime.activity import activity
from app.runtime.status_copy import (
  DISMISSED_FOLLOW_UP_TITLE,
  NOTED_FOR_LATER_TITLE,
  RESCHEDULED_FOLLOW_UP_TITLE,
)


class InternalNoteService:
  """High-level API for Nano's private follow-up notes."""

  def record_from_offer(
    self,
    offer: ProactiveOffer,
    *,
    next_attempt_at: datetime | None = None,
  ) -> InternalNote:
    settings = get_settings()
    scheduled_at = next_attempt_at or datetime.now(UTC) + timedelta(
      seconds=settings.internal_note_retry_interval_seconds
    )
    note = internal_notes.add_internal_note(
      kind=offer.kind,
      title=offer.title,
      content=offer.summary,
      payload_json=offer.to_json(),
      next_attempt_at=scheduled_at,
    )
    activity.log(
      title=NOTED_FOR_LATER_TITLE,
      detail=offer.title,
      source="memory.internal_notes",
    )
    return note

  def record_deferred_offer(
    self,
    offer: ProactiveOffer,
    *,
    reason: str,
    note_id: int | None = None,
  ) -> InternalNote:
    if note_id is not None:
      existing = internal_notes.get_internal_note(note_id)
      if existing is not None:
        return self._reschedule_existing(existing, reason=reason)
    return self.record_from_offer(offer)

  def offer_from_internal_note(self, note: InternalNote) -> ProactiveOffer:
    return ProactiveOffer.from_json(note.payload_json)

  def top_pending_self_improvement_note(self) -> InternalNote | None:
    notes = internal_notes.list_pending_self_improvement_notes(limit=1)
    return notes[0] if notes else None

  def goal_from_internal_note(self, note: InternalNote) -> str:
    offer = self.offer_from_internal_note(note)
    goal = str(offer.payload.get("goal", "")).strip()
    if goal:
      return goal
    return offer.summary.strip()

  def resolve_self_improve_goal(self, explicit_goal: str) -> tuple[str, int | None]:
    cleaned = " ".join(explicit_goal.strip().split())
    if not is_vague_self_improve_goal(cleaned):
      return cleaned, None

    note = self.top_pending_self_improvement_note()
    if note is None or note.id is None:
      return "general improvement", None

    return self.goal_from_internal_note(note), note.id

  def top_priority_due_note(self, *, now: datetime | None = None) -> InternalNote | None:
    due = internal_notes.list_due_internal_notes(now=now, limit=1)
    return due[0] if due else None

  def list_due_notes(self, *, now: datetime | None = None) -> list[InternalNote]:
    return internal_notes.list_due_internal_notes(now=now, limit=10)

  def mark_attempted(self, note_id: int) -> None:
    internal_notes.mark_internal_note_attempted(note_id)

  def mark_delivered(self, note_id: int) -> None:
    internal_notes.mark_internal_note_delivered(note_id)

  def _reschedule_existing(self, note: InternalNote, *, reason: str) -> InternalNote:
    settings = get_settings()
    next_count = note.attempt_count + 1
    if next_count >= settings.internal_note_max_attempts:
      internal_notes.dismiss_internal_note(note.id or 0)
      activity.log(
        title=DISMISSED_FOLLOW_UP_TITLE,
        detail=f"{note.title} ({reason})",
        source="memory.internal_notes",
      )
      return note

    base = settings.internal_note_retry_interval_seconds
    max_interval = settings.internal_note_retry_max_interval_seconds
    delay = min(base * (2 ** note.attempt_count), max_interval)
    next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
    internal_notes.reschedule_internal_note(note.id or 0, next_attempt_at=next_attempt_at)
    internal_notes.mark_internal_note_attempted(note.id or 0)
    activity.log(
      title=RESCHEDULED_FOLLOW_UP_TITLE,
      detail=f"{note.title} ({reason})",
      source="memory.internal_notes",
    )
    refreshed = internal_notes.get_internal_note(note.id or 0)
    return refreshed or note


internal_note_service = InternalNoteService()
