from datetime import UTC, datetime

from sqlmodel import Session, col, desc, select

import app.memory.db as db
from app.memory.models import (
    ChatMessage,
    CodebaseFileRecord,
    ImprovementPlan,
    InternalNote,
    Timer,
)


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


def add_timer(label: str, due_at: datetime) -> Timer:
    """
    Add timer.

    Args:
        label: Timer label.
        due_at: Timer due timestamp.

    Returns:
        Timer result.
    """
    with Session(db.engine) as session:
        timer = Timer(label=label or "Timer", due_at=due_at)
        session.add(timer)
        session.commit()
        session.refresh(timer)
        return timer


def list_timers() -> list[Timer]:
    """
    List active timers.

    Returns:
        List of matching records or values.
    """
    statement = select(Timer).order_by(col(Timer.due_at), col(Timer.id))
    with Session(db.engine) as session:
        return list(session.exec(statement))


def list_due_timers(now: datetime | None = None) -> list[Timer]:
    """
    List due timers.

    Args:
        now: Current timestamp used for time-based filtering.

    Returns:
        List of matching records or values.
    """
    current_time = now or datetime.now(UTC)
    statement = (
        select(Timer)
        .where(col(Timer.due_at) <= current_time)
        .order_by(col(Timer.due_at), col(Timer.id))
    )
    with Session(db.engine) as session:
        return list(session.exec(statement))


def delete_timer(timer_id: int) -> bool:
    """
    Delete timer.

    Args:
        timer_id: Timer id value.

    Returns:
        True when the condition is met; otherwise false.
    """
    with Session(db.engine) as session:
        timer = session.get(Timer, timer_id)
        if timer is None:
            return False
        session.delete(timer)
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
            Timer,
            InternalNote,
            ImprovementPlan,
            CodebaseFileRecord,
        ):
            rows = list(session.exec(select(model)))
            for row in rows:
                session.delete(row)
        session.commit()
