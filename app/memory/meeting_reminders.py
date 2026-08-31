from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Session, col, delete, select

import app.memory.db as db
from app.memory.models import MeetingReminder


def _new_reminder_id() -> str:
    return f"rem_{uuid.uuid4().hex[:20]}"


def get_reminder(reminder_id: str) -> MeetingReminder | None:
    with Session(db.get_engine()) as session:
        return session.get(MeetingReminder, reminder_id)


def get_reminder_by_key(
    calendar_id: str,
    event_id: str,
    start: datetime,
) -> MeetingReminder | None:
    statement = select(MeetingReminder).where(
        MeetingReminder.calendar_id == calendar_id,
        MeetingReminder.event_id == event_id,
        MeetingReminder.start == start,
    )
    with Session(db.get_engine()) as session:
        return session.exec(statement).first()


def upsert_reminder(
    *,
    calendar_id: str,
    event_id: str,
    start: datetime,
    end: datetime,
    summary: str,
    all_day: bool,
    lead_minutes: int,
    remind_at: datetime,
) -> MeetingReminder:
    now = datetime.now(UTC)
    with Session(db.get_engine()) as session:
        statement = select(MeetingReminder).where(
            MeetingReminder.calendar_id == calendar_id,
            MeetingReminder.event_id == event_id,
            MeetingReminder.start == start,
        )
        existing = session.exec(statement).first()
        if existing is not None:
            existing.end = end
            existing.summary = summary
            existing.all_day = all_day
            existing.lead_minutes = lead_minutes
            existing.remind_at = remind_at
            existing.fired_at = None
            existing.updated_at = now
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        reminder = MeetingReminder(
            id=_new_reminder_id(),
            calendar_id=calendar_id,
            event_id=event_id,
            start=start,
            end=end,
            summary=summary,
            all_day=all_day,
            lead_minutes=lead_minutes,
            remind_at=remind_at,
            created_at=now,
            updated_at=now,
        )
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return reminder


def list_active_reminders(now: datetime) -> list[MeetingReminder]:
    statement = (
        select(MeetingReminder)
        .where(col(MeetingReminder.fired_at).is_(None))
        .where(col(MeetingReminder.start) > now)
        .order_by(col(MeetingReminder.start))
    )
    with Session(db.get_engine()) as session:
        return list(session.exec(statement))


def list_schedulable_reminders(now: datetime) -> list[MeetingReminder]:
    statement = (
        select(MeetingReminder)
        .where(col(MeetingReminder.fired_at).is_(None))
        .where(col(MeetingReminder.remind_at) > now)
        .order_by(col(MeetingReminder.remind_at))
    )
    with Session(db.get_engine()) as session:
        return list(session.exec(statement))


def list_due_reminders(now: datetime) -> list[MeetingReminder]:
    statement = (
        select(MeetingReminder)
        .where(col(MeetingReminder.fired_at).is_(None))
        .where(col(MeetingReminder.remind_at) <= now)
        .order_by(col(MeetingReminder.remind_at))
    )
    with Session(db.get_engine()) as session:
        return list(session.exec(statement))


def delete_reminder_by_key(
    calendar_id: str,
    event_id: str,
    start: datetime,
) -> MeetingReminder | None:
    with Session(db.get_engine()) as session:
        statement = select(MeetingReminder).where(
            MeetingReminder.calendar_id == calendar_id,
            MeetingReminder.event_id == event_id,
            MeetingReminder.start == start,
        )
        reminder = session.exec(statement).first()
        if reminder is None:
            return None
        session.delete(reminder)
        session.commit()
        return reminder


def mark_reminder_fired(
    reminder_id: str, fired_at: datetime | None = None
) -> MeetingReminder | None:
    current = fired_at or datetime.now(UTC)
    with Session(db.get_engine()) as session:
        reminder = session.get(MeetingReminder, reminder_id)
        if reminder is None:
            return None
        reminder.fired_at = current
        reminder.updated_at = current
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return reminder


def prune_expired_reminders(now: datetime) -> int:
    statement = delete(MeetingReminder).where(col(MeetingReminder.start) <= now)
    with Session(db.get_engine()) as session:
        result = session.exec(statement)
        session.commit()
        return result.rowcount or 0
