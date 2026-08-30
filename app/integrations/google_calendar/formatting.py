from __future__ import annotations

from typing import Any

from app.integrations.google_calendar.client import get_event_start


def format_available_calendars(calendars: list[dict[str, str]]) -> str:
    if not calendars:
        return "No calendars found."

    lines = ["Available calendars:"]
    for index, calendar in enumerate(calendars, start=1):
        label = calendar["summary"]
        if calendar.get("primary") == "true":
            label = f"{label} (primary)"
        lines.append(f"{index}. {label} — id: {calendar['id']}")

    return "\n".join(lines)


def format_upcoming_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No upcoming events."

    calendar_labels = {
        event.get("_calendar_summary")
        for event in events
        if isinstance(event.get("_calendar_summary"), str)
    }
    show_calendar_labels = len(calendar_labels) > 1

    lines: list[str] = []
    for event in events:
        title = event.get("summary", "(Untitled event)")
        start = get_event_start(event)
        if show_calendar_labels:
            calendar_name = event.get("_calendar_summary", "Calendar")
            lines.append(f"{start} [{calendar_name}]: {title}")
        else:
            lines.append(f"{start}: {title}")

    return "\n".join(lines)
