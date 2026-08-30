from __future__ import annotations

from typing import Any

from googleapiclient.errors import HttpError

from app.integrations.google_calendar import (
    GoogleCalendarAuthenticationError,
    GoogleCalendarNotFoundError,
    format_available_calendars,
    format_upcoming_events,
    list_available_calendars,
    list_upcoming_events,
)
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _parse_maximum_results(args: dict[str, Any]) -> int:
    raw = args.get("maximum_results", 10)
    if isinstance(raw, bool):
        raise ValueError("maximum_results must be an integer.")
    if isinstance(raw, int):
        return min(2500, max(1, raw))
    if isinstance(raw, str) and raw.isdigit():
        return min(2500, max(1, int(raw)))
    return 10


def _optional_calendar_id(args: dict[str, Any]) -> str | None:
    raw = args.get("calendar_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _list_upcoming_calendar_events(args: dict[str, Any]) -> str:
    """
    List upcoming events from configured or requested Google calendars.

    Args:
        args: Optional tool arguments with maximum_results and calendar_id.

    Returns:
        Human-readable list of upcoming events.
    """
    maximum_results = _parse_maximum_results(args)
    calendar_id = _optional_calendar_id(args)

    try:
        events = list_upcoming_events(
            maximum_results=maximum_results,
            calendar_id=calendar_id,
        )
    except GoogleCalendarNotFoundError:
        calendars = list_available_calendars()
        return (
            "That calendar was not found. Available calendars:\n"
            f"{format_available_calendars(calendars)}"
        )
    except GoogleCalendarAuthenticationError as exc:
        return str(exc)
    except HttpError as exc:
        return f"Google Calendar API request failed: {exc}"

    return format_upcoming_events(events)


def _list_google_calendars(_args: dict[str, Any]) -> str:
    """
    List Google calendars available to the authorized account.

    Args:
        _args: Unused tool arguments.

    Returns:
        Human-readable list of calendars and IDs.
    """
    try:
        calendars = list_available_calendars()
    except GoogleCalendarAuthenticationError as exc:
        return str(exc)
    except HttpError as exc:
        return f"Google Calendar API request failed: {exc}"

    return format_available_calendars(calendars)


register_tool(
    ToolSpec(
        name="list_upcoming_calendar_events",
        description=(
            "List upcoming events from configured Google calendars. "
            "Uses GOOGLE_CALENDAR_IDS by default; pass calendar_id to target one calendar."
        ),
        args_schema={
            "maximum_results": "optional int, default 10",
            "calendar_id": "optional calendar ID override",
        },
        handler=_list_upcoming_calendar_events,
        announcement="Checking your calendar.",
        keywords=(
            "calendar",
            "event",
            "schedule",
            "appointment",
            "meeting",
        ),
    )
)

register_tool(
    ToolSpec(
        name="list_google_calendars",
        description=(
            "List Google calendars available to this account with their IDs for .env configuration."
        ),
        args_schema={},
        handler=_list_google_calendars,
        announcement="Listing your Google calendars.",
        keywords=(
            "google calendar",
            "calendars",
        ),
    )
)
