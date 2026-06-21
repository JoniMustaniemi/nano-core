from datetime import UTC, datetime

from sqlmodel import Session, desc, select

import app.memory.db as db
from app.memory.models import ChatMessage, Note, Reminder
from app.runtime.activity import activity


def add_note(content: str) -> Note:
    with Session(db.engine) as session:
        note = Note(content=content)
        session.add(note)
        session.commit()
        session.refresh(note)
        activity.log(
            title="Nano saved a note.",
            detail=f"Stored note #{note.id}.",
            source="memory.notes",
        )
        return note


def list_notes(limit: int | None = None) -> list[Note]:
    statement = select(Note).order_by(desc(Note.created_at))
    if limit is not None:
        statement = statement.limit(limit)
    with Session(db.engine) as session:
        return list(session.exec(statement))


def add_chat_message(conversation_id: str, role: str, content: str) -> ChatMessage:
    with Session(db.engine) as session:
        message = ChatMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        session.add(message)
        session.commit()
        session.refresh(message)
        return message


def list_chat_messages(
    conversation_id: str,
    limit: int = 20,
) -> list[ChatMessage]:
    statement = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        .limit(limit)
    )
    with Session(db.engine) as session:
        rows = list(session.exec(statement))
    return list(reversed(rows))


def list_recent_chat_messages(limit: int = 20) -> list[ChatMessage]:
    statement = (
        select(ChatMessage)
        .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        .limit(limit)
    )
    with Session(db.engine) as session:
        rows = list(session.exec(statement))
    return list(reversed(rows))


def add_reminder(content: str, due_at: datetime) -> Reminder:
    with Session(db.engine) as session:
        reminder = Reminder(content=content, due_at=due_at)
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        activity.log(
            title="Nano scheduled a reminder.",
            detail=f"Reminder #{reminder.id} due at {reminder.due_at.isoformat()}.",
            source="memory.reminders",
        )
        return reminder


def list_reminders(*, include_sent: bool = False) -> list[Reminder]:
    statement = select(Reminder).order_by(desc(Reminder.due_at), desc(Reminder.id))
    if not include_sent:
        statement = statement.where(Reminder.sent_at.is_(None))
    with Session(db.engine) as session:
        return list(session.exec(statement))


def list_due_reminders(now: datetime | None = None) -> list[Reminder]:
    current_time = now or datetime.now(UTC)
    statement = (
        select(Reminder)
        .where(Reminder.due_at <= current_time)
        .where(Reminder.sent_at.is_(None))
        .order_by(Reminder.due_at, Reminder.id)
    )
    with Session(db.engine) as session:
        return list(session.exec(statement))


def mark_reminder_sent(reminder_id: int, sent_at: datetime | None = None) -> Reminder | None:
    timestamp = sent_at or datetime.now(UTC)
    with Session(db.engine) as session:
        reminder = session.get(Reminder, reminder_id)
        if reminder is None:
            return None
        reminder.sent_at = timestamp
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        return reminder


def delete_reminder(reminder_id: int) -> bool:
    with Session(db.engine) as session:
        reminder = session.get(Reminder, reminder_id)
        if reminder is None:
            return False
        session.delete(reminder)
        session.commit()
        return True


def wipe_database() -> None:
    with Session(db.engine) as session:
        for model in (ChatMessage, Note, Reminder):
            rows = list(session.exec(select(model)))
            for row in rows:
                session.delete(row)
        session.commit()
