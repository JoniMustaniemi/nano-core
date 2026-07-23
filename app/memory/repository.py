from datetime import UTC, datetime

from sqlmodel import Session, col, desc, select

import app.memory.db as db
from app.memory.models import (
    ChatMessage,
    CodebaseFileRecord,
    ImprovementPlan,
    InternalNote,
    Note,
    Reminder,
)
from app.runtime.activity import activity
from app.runtime.status_copy import SAVED_NOTE_TITLE, SCHEDULED_REMINDER_TITLE


def add_note(content: str, name: str = "Untitled note") -> Note:
    """
    Add note.

    Args:
        content: Text content to persist or return.
        name: Note name.

    Returns:
        Note result.
    """
    with Session(db.engine) as session:
        note = Note(name=name, content=content)
        session.add(note)
        session.commit()
        session.refresh(note)
        activity.log(
            title=SAVED_NOTE_TITLE,
            detail=f"Stored note #{note.id}.",
            source="memory.notes",
        )
        return note


def list_notes(limit: int | None = None) -> list[Note]:
    """
    List notes.

    Args:
        limit: Maximum number of records to return.

    Returns:
        List of matching records or values.
    """
    statement = select(Note).order_by(desc(Note.created_at))
    if limit is not None:
        statement = statement.limit(limit)
    with Session(db.engine) as session:
        return list(session.exec(statement))


def add_chat_message(conversation_id: str, role: str, content: str) -> ChatMessage:
    """
    Add chat message.

    Args:
        conversation_id: Conversation identifier used to scope history and pending state.
        role: Role value.
        content: Text content to persist or return.

    Returns:
        ChatMessage result.
    """
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
    """
    List chat messages.

    Args:
        conversation_id: Conversation identifier used to scope history and pending state.
        limit: Maximum number of records to return.

    Returns:
        List of matching records or values.
    """
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
    """
    List recent chat messages.

    Args:
        limit: Maximum number of records to return.

    Returns:
        List of matching records or values.
    """
    statement = (
        select(ChatMessage)
        .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        .limit(limit)
    )
    with Session(db.engine) as session:
        rows = list(session.exec(statement))
    return list(reversed(rows))


def add_reminder(content: str, due_at: datetime) -> Reminder:
    """
    Add reminder.

    Args:
        content: Text content to persist or return.
        due_at: Reminder or timer due timestamp.

    Returns:
        Reminder result.
    """
    with Session(db.engine) as session:
        reminder = Reminder(content=content, due_at=due_at)
        session.add(reminder)
        session.commit()
        session.refresh(reminder)
        activity.log(
            title=SCHEDULED_REMINDER_TITLE,
            detail=f"Reminder #{reminder.id} due at {reminder.due_at.isoformat()}.",
            source="memory.reminders",
        )
        return reminder


def list_reminders(*, include_sent: bool = False) -> list[Reminder]:
    """
    List reminders.

    Args:
        include_sent: Whether sent reminders should be included.

    Returns:
        List of matching records or values.
    """
    statement = select(Reminder).order_by(desc(col(Reminder.due_at)), desc(col(Reminder.id)))
    if not include_sent:
        statement = statement.where(col(Reminder.sent_at).is_(None))
    with Session(db.engine) as session:
        return list(session.exec(statement))


def list_due_reminders(now: datetime | None = None) -> list[Reminder]:
    """
    List due reminders.

    Args:
        now: Current timestamp used for time-based filtering.

    Returns:
        List of matching records or values.
    """
    current_time = now or datetime.now(UTC)
    statement = (
        select(Reminder)
        .where(col(Reminder.due_at) <= current_time)
        .where(col(Reminder.sent_at).is_(None))
        .order_by(col(Reminder.due_at), col(Reminder.id))
    )
    with Session(db.engine) as session:
        return list(session.exec(statement))


def mark_reminder_sent(reminder_id: int, sent_at: datetime | None = None) -> Reminder | None:
    """
    Mark reminder sent.

    Args:
        reminder_id: Reminder id value.
        sent_at: Timestamp to record as the sent time.

    Returns:
        Parsed value when available; otherwise None.
    """
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
    """
    Delete reminder.

    Args:
        reminder_id: Reminder id value.

    Returns:
        True when the condition is met; otherwise false.
    """
    with Session(db.engine) as session:
        reminder = session.get(Reminder, reminder_id)
        if reminder is None:
            return False
        session.delete(reminder)
        session.commit()
        return True


def wipe_database() -> None:
    """
    Wipe database.

    Returns:
        None.
    """
    with Session(db.engine) as session:
        for model in (
            ChatMessage,
            Note,
            Reminder,
            InternalNote,
            ImprovementPlan,
            CodebaseFileRecord,
        ):
            rows = list(session.exec(select(model)))
            for row in rows:
                session.delete(row)
        session.commit()
