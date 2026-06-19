from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.memory.models import Note, Reminder
from app.memory.repository import add_note, add_reminder, list_notes, list_reminders

router = APIRouter(prefix="/api", tags=["memory"])


class NoteCreate(BaseModel):
    content: str = Field(min_length=1)


class ReminderCreate(BaseModel):
    content: str = Field(min_length=1)
    due_at: datetime


@router.get("/notes", response_model=list[Note])
def read_notes() -> list[Note]:
    return list_notes()


@router.post("/notes", response_model=Note)
def create_note(payload: NoteCreate) -> Note:
    return add_note(payload.content)


@router.get("/reminders", response_model=list[Reminder])
def read_reminders() -> list[Reminder]:
    return list_reminders()


@router.post("/reminders", response_model=Reminder)
def create_reminder(payload: ReminderCreate) -> Reminder:
    if payload.due_at.tzinfo is None:
        raise HTTPException(status_code=400, detail="due_at must include timezone information.")
    return add_reminder(payload.content, payload.due_at)
