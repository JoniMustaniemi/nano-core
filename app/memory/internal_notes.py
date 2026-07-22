from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, col, select

import app.memory.db as db
from app.memory.models import InternalNote


def add_internal_note(
    *,
    kind: str,
    title: str,
    content: str,
    payload_json: str,
    next_attempt_at: datetime,
) -> InternalNote:
  with Session(db.engine) as session:
    note = InternalNote(
      kind=kind,
      title=title,
      content=content,
      payload_json=payload_json,
      status="pending",
      next_attempt_at=next_attempt_at,
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


def get_internal_note(note_id: int) -> InternalNote | None:
  with Session(db.engine) as session:
    return session.get(InternalNote, note_id)


def list_due_internal_notes(
    *,
    now: datetime | None = None,
    limit: int = 1,
) -> list[InternalNote]:
  current = now or datetime.now(UTC)
  statement = (
    select(InternalNote)
    .where(InternalNote.status == "pending")
    .where(InternalNote.next_attempt_at <= current)
    .order_by(col(InternalNote.next_attempt_at), col(InternalNote.created_at))
    .limit(limit)
  )
  with Session(db.engine) as session:
    return list(session.exec(statement))


def list_internal_notes(*, limit: int = 50) -> list[InternalNote]:
  statement = (
    select(InternalNote)
    .order_by(col(InternalNote.created_at).desc())
    .limit(limit)
  )
  with Session(db.engine) as session:
    return list(session.exec(statement))


def mark_internal_note_attempted(note_id: int, *, attempted_at: datetime | None = None) -> None:
  current = attempted_at or datetime.now(UTC)
  with Session(db.engine) as session:
    note = session.get(InternalNote, note_id)
    if note is None:
      return
    note.attempt_count += 1
    note.last_attempt_at = current
    session.add(note)
    session.commit()


def reschedule_internal_note(note_id: int, *, next_attempt_at: datetime) -> None:
  with Session(db.engine) as session:
    note = session.get(InternalNote, note_id)
    if note is None:
      return
    note.next_attempt_at = next_attempt_at
    session.add(note)
    session.commit()


def mark_internal_note_delivered(note_id: int, *, delivered_at: datetime | None = None) -> None:
  current = delivered_at or datetime.now(UTC)
  with Session(db.engine) as session:
    note = session.get(InternalNote, note_id)
    if note is None:
      return
    note.status = "delivered"
    note.delivered_at = current
    session.add(note)
    session.commit()


def dismiss_internal_note(note_id: int) -> None:
  with Session(db.engine) as session:
    note = session.get(InternalNote, note_id)
    if note is None:
      return
    note.status = "dismissed"
    session.add(note)
    session.commit()
