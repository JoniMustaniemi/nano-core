from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.integrations.google_calendar import (
    GoogleCalendarAuthenticationError,
    GoogleCalendarNotFoundError,
    configured_calendar_ids,
    list_available_calendars,
    list_events_in_range,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


class CalendarSummary(BaseModel):
    id: str
    summary: str
    primary: bool
    background_color: str | None = None


class CalendarDefaultResponse(BaseModel):
    calendar_id: str


class CalendarEventResponse(BaseModel):
    id: str
    summary: str
    start: str
    end: str
    all_day: bool
    html_link: str | None = None
    calendar_id: str | None = None
    calendar_summary: str | None = None
    calendar_color: str | None = None


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field_name}. Use an ISO-8601 datetime.",
        ) from exc


@router.get("/calendars", response_model=list[CalendarSummary])
def read_calendars() -> list[CalendarSummary]:
    try:
        calendars = list_available_calendars()
    except GoogleCalendarAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return [
        CalendarSummary(
            id=calendar["id"],
            summary=calendar["summary"],
            primary=calendar.get("primary") == "true",
            background_color=calendar.get("background_color"),
        )
        for calendar in calendars
    ]


@router.get("/default", response_model=CalendarDefaultResponse)
def read_default_calendar() -> CalendarDefaultResponse:
    return CalendarDefaultResponse(calendar_id=configured_calendar_ids()[0])


@router.get("/events", response_model=list[CalendarEventResponse])
def read_calendar_events(
    calendar_id: str | None = Query(default=None),
    time_min: str = Query(...),
    time_max: str = Query(...),
) -> list[CalendarEventResponse]:
    target_calendar_id = calendar_id or configured_calendar_ids()[0]
    parsed_time_min = _parse_datetime(time_min, "time_min")
    parsed_time_max = _parse_datetime(time_max, "time_max")

    if parsed_time_max <= parsed_time_min:
        raise HTTPException(status_code=422, detail="time_max must be after time_min.")

    try:
        events = list_events_in_range(
            target_calendar_id,
            parsed_time_min,
            parsed_time_max,
        )
    except GoogleCalendarAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GoogleCalendarNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return [CalendarEventResponse.model_validate(event) for event in events]
