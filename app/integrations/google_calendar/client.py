from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from googleapiclient.discovery import Resource

from app.integrations.google_calendar.auth import (
    GoogleCalendarNotFoundError,
    configured_calendar_ids,
    get_calendar_service,
)


def list_available_calendars() -> list[dict[str, str]]:
    service = get_calendar_service()
    response = service.calendarList().list().execute()
    items = response.get("items", [])
    if not isinstance(items, list):
        return []

    calendars: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        calendar_id = item.get("id")
        if not isinstance(calendar_id, str) or not calendar_id:
            continue
        summary = item.get("summary", calendar_id)
        primary = "true" if item.get("primary") else "false"
        background_color = item.get("backgroundColor")
        calendar: dict[str, str] = {
            "id": calendar_id,
            "summary": summary if isinstance(summary, str) else calendar_id,
            "primary": primary,
        }
        if isinstance(background_color, str):
            calendar["background_color"] = background_color
        calendars.append(calendar)

    return calendars


def resolve_calendar_ids(calendar_id: str | None = None) -> list[str]:
    if calendar_id:
        return [calendar_id]
    return configured_calendar_ids()


def _calendar_lookup(calendars: list[dict[str, str]]) -> dict[str, str]:
    return {calendar["id"]: calendar["summary"] for calendar in calendars}


def _validate_calendar_ids(
    calendar_ids: list[str],
    calendars: list[dict[str, str]],
) -> None:
    available_ids = {calendar["id"] for calendar in calendars}
    missing = [calendar_id for calendar_id in calendar_ids if calendar_id not in available_ids]
    if missing:
        raise GoogleCalendarNotFoundError(missing[0])


def get_event_start(event: dict[str, Any]) -> str:
    start = event.get("start", {})
    return start.get("dateTime") or start.get("date") or "Unknown start time"


def _parse_event_start_for_sort(event: dict[str, Any]) -> datetime:
    start = event.get("start", {})
    date_time = start.get("dateTime")
    if isinstance(date_time, str):
        try:
            parsed = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            pass

    date_value = start.get("date")
    if isinstance(date_value, str):
        try:
            parsed = datetime.fromisoformat(date_value)
            return parsed.replace(tzinfo=UTC)
        except ValueError:
            pass

    return datetime.max.replace(tzinfo=UTC)


def _event_sort_key(event: dict[str, Any]) -> datetime:
    return _parse_event_start_for_sort(event)


def _fetch_events_for_calendar(
    service: Resource,
    calendar_id: str,
    *,
    time_min: str,
    maximum_results: int,
    time_max: str | None = None,
) -> list[dict[str, Any]]:
    request_kwargs: dict[str, Any] = {
        "calendarId": calendar_id,
        "timeMin": time_min,
        "maxResults": maximum_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }
    if time_max is not None:
        request_kwargs["timeMax"] = time_max

    response = service.events().list(**request_kwargs).execute()

    items = response.get("items", [])
    if not isinstance(items, list):
        return []

    return cast(list[dict[str, Any]], items)


def _normalize_calendar_event(event: dict[str, Any]) -> dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    start_value = start.get("dateTime") or start.get("date") or ""
    end_value = end.get("dateTime") or end.get("date") or ""
    all_day = "date" in start and "dateTime" not in start
    html_link = event.get("htmlLink")
    return {
        "id": event.get("id", ""),
        "summary": event.get("summary", "(Untitled event)"),
        "start": start_value if isinstance(start_value, str) else "",
        "end": end_value if isinstance(end_value, str) else "",
        "all_day": all_day,
        "html_link": html_link if isinstance(html_link, str) else None,
    }


def _calendar_color_lookup(calendars: list[dict[str, str]]) -> dict[str, str | None]:
    return {calendar["id"]: calendar.get("background_color") for calendar in calendars}


def _normalize_calendar_event_with_meta(
    event: dict[str, Any],
    *,
    calendar_id: str,
    calendar_summary: str,
    calendar_color: str | None,
) -> dict[str, Any]:
    normalized = _normalize_calendar_event(event)
    normalized["calendar_id"] = calendar_id
    normalized["calendar_summary"] = calendar_summary
    normalized["calendar_color"] = calendar_color
    return normalized


def list_events_in_range(
    calendar_id: str,
    time_min: datetime,
    time_max: datetime,
) -> list[dict[str, Any]]:
    if time_min.tzinfo is None or time_min.tzinfo.utcoffset(time_min) is None:
        raise ValueError("time_min must include timezone information.")
    if time_max.tzinfo is None or time_max.tzinfo.utcoffset(time_max) is None:
        raise ValueError("time_max must include timezone information.")
    if time_max <= time_min:
        raise ValueError("time_max must be after time_min.")

    service = get_calendar_service()
    calendars = list_available_calendars()
    _validate_calendar_ids([calendar_id], calendars)
    summaries = _calendar_lookup(calendars)
    colors = _calendar_color_lookup(calendars)

    raw_events = _fetch_events_for_calendar(
        service,
        calendar_id,
        time_min=time_min.isoformat(),
        time_max=time_max.isoformat(),
        maximum_results=2500,
    )
    return [
        _normalize_calendar_event_with_meta(
            event,
            calendar_id=calendar_id,
            calendar_summary=summaries.get(calendar_id, calendar_id),
            calendar_color=colors.get(calendar_id),
        )
        for event in raw_events
    ]


def list_upcoming_events(
    maximum_results: int = 10,
    calendar_id: str | None = None,
) -> list[dict[str, Any]]:
    service = get_calendar_service()
    calendars = list_available_calendars()
    calendar_ids = resolve_calendar_ids(calendar_id)
    _validate_calendar_ids(calendar_ids, calendars)
    summaries = _calendar_lookup(calendars)

    now = datetime.now(UTC).isoformat()
    merged_events: list[dict[str, Any]] = []

    for target_calendar_id in calendar_ids:
        events = _fetch_events_for_calendar(
            service,
            target_calendar_id,
            time_min=now,
            maximum_results=maximum_results,
        )
        summary = summaries.get(target_calendar_id, target_calendar_id)
        for event in events:
            event["_calendar_id"] = target_calendar_id
            event["_calendar_summary"] = summary
            merged_events.append(event)

    merged_events.sort(key=_event_sort_key)
    return merged_events[:maximum_results]
