from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.memory.models import ChatMessage, Note, Reminder
from app.memory.repository import (
    add_note,
    add_reminder,
    list_notes,
    list_recent_chat_messages,
    list_reminders,
)

router = APIRouter(prefix="/api", tags=["memory"])


class NoteCreate(BaseModel):
    content: str = Field(min_length=1)


class ReminderCreate(BaseModel):
    content: str = Field(min_length=1)
    due_at: datetime


class StorageSnapshot(BaseModel):
    notes: list[Note]
    reminders: list[Reminder]
    chat_messages: list[ChatMessage]


@router.get("/notes", response_model=list[Note])
def read_notes() -> list[Note]:
    """
    Read notes.

    Returns:
        List of matching records or values.
    """
    return list_notes()


@router.post("/notes", response_model=Note)
def create_note(payload: NoteCreate) -> Note:
    """
    Create note.

    Args:
        payload: Validated request payload.

    Returns:
        Note result.
    """
    return add_note(payload.content)


@router.get("/reminders", response_model=list[Reminder])
def read_reminders() -> list[Reminder]:
    """
    Read reminders.

    Returns:
        List of matching records or values.
    """
    return list_reminders()


@router.post("/reminders", response_model=Reminder)
def create_reminder(payload: ReminderCreate) -> Reminder:
    """
    Create reminder.

    Args:
        payload: Validated request payload.

    Returns:
        Reminder result.

    Raises:
        HTTPException: If the operation cannot be completed.
    """
    if payload.due_at.tzinfo is None:
        raise HTTPException(status_code=400, detail="due_at must include timezone information.")
    return add_reminder(payload.content, payload.due_at)


@router.get("/storage", response_model=StorageSnapshot)
def read_storage_snapshot() -> StorageSnapshot:
    """
    Read storage snapshot.

    Returns:
        StorageSnapshot result.
    """
    return StorageSnapshot(
        notes=list_notes(),
        reminders=list_reminders(include_sent=True),
        chat_messages=list_recent_chat_messages(),
    )
