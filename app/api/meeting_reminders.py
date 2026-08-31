from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.integrations.google_calendar import GoogleCalendarAuthenticationError
from app.meeting_reminders.service import (
    delete_meeting_reminder,
    ensure_calendar_connected,
    list_meeting_reminders,
    upsert_meeting_reminder,
)
from app.meeting_reminders.validation import (
    MeetingReminderDatetimeError,
    MeetingReminderValidationError,
)

router = APIRouter(tags=["calendar"])


class MeetingReminderResponse(BaseModel):
    id: str
    calendar_id: str
    event_id: str
    start: str
    end: str
    summary: str
    all_day: bool
    lead_minutes: int
    remind_at: str
    fired_at: str | None
    created_at: str
    updated_at: str


class MeetingReminderUpsert(BaseModel):
    calendar_id: str
    event_id: str
    start: str
    end: str
    summary: str
    all_day: bool
    lead_minutes: Literal[15, 30, 60]


def _handle_calendar_errors(exc: Exception) -> None:
    if isinstance(exc, GoogleCalendarAuthenticationError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, MeetingReminderDatetimeError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, MeetingReminderValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/meeting-reminders", response_model=list[MeetingReminderResponse])
def read_meeting_reminders() -> list[MeetingReminderResponse]:
    try:
        ensure_calendar_connected()
        reminders = list_meeting_reminders()
    except Exception as exc:
        _handle_calendar_errors(exc)
    return [MeetingReminderResponse.model_validate(reminder) for reminder in reminders]


@router.put("/meeting-reminders", response_model=MeetingReminderResponse)
def upsert_meeting_reminder_route(body: MeetingReminderUpsert) -> MeetingReminderResponse:
    try:
        ensure_calendar_connected()
        reminder = upsert_meeting_reminder(
            calendar_id=body.calendar_id,
            event_id=body.event_id,
            start_raw=body.start,
            end_raw=body.end,
            summary=body.summary,
            all_day=body.all_day,
            lead_minutes=body.lead_minutes,
        )
    except Exception as exc:
        _handle_calendar_errors(exc)
    return MeetingReminderResponse.model_validate(reminder)


@router.delete("/meeting-reminders", status_code=204)
def delete_meeting_reminder_route(
    calendar_id: str = Query(...),
    event_id: str = Query(...),
    start: str = Query(...),
) -> None:
    try:
        ensure_calendar_connected()
        delete_meeting_reminder(calendar_id, event_id, start)
    except Exception as exc:
        _handle_calendar_errors(exc)
