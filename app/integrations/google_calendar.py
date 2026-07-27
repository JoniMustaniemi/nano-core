from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from app.config import get_settings

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
]


class GoogleCalendarAuthenticationError(RuntimeError):
    pass


class GoogleCalendarNotFoundError(RuntimeError):
    pass


def _credentials_path() -> Path:
    return Path(get_settings().google_credentials_path)


def _token_path() -> Path:
    return Path(get_settings().google_token_path)


def configured_calendar_ids() -> list[str]:
    """
    Return configured Google Calendar IDs from settings.

    Returns:
        Non-empty list of calendar IDs. Defaults to primary when unset.
    """
    raw = get_settings().google_calendar_ids.strip()
    if not raw:
        return ["primary"]
    return [part.strip() for part in raw.split(",") if part.strip()]


def run_authorization_flow() -> Path:
    """
    Run the one-time OAuth browser flow and write token.json.

    Returns:
        Path to the created token file.

    Raises:
        FileNotFoundError: When credentials.json is missing.
    """
    credentials_file = _credentials_path()
    token_file = _token_path()

    if not credentials_file.exists():
        raise FileNotFoundError(f"Missing file: {credentials_file}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        scopes=SCOPES,
    )

    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        authorization_prompt_message="Open this URL in a browser:\n{url}",
        success_message="Authorization completed. You may close this window.",
    )

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    return token_file


def get_calendar_service() -> Resource:
    """
    Build an authenticated Google Calendar API client.

    Returns:
        Google Calendar API service resource.

    Raises:
        GoogleCalendarAuthenticationError: When token is missing, invalid, or cannot refresh.
    """
    token_file = _token_path()

    if not token_file.exists():
        raise GoogleCalendarAuthenticationError(
            "token.json is missing. Run `nano-core auth-google-calendar` "
            "or `python scripts/google_calendar_auth.py` to authorize."
        )

    try:
        credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(token_file),
            SCOPES,
        )
    except (OSError, ValueError) as exc:
        raise GoogleCalendarAuthenticationError(f"Could not read token.json: {exc}") from exc

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as exc:
            raise GoogleCalendarAuthenticationError(
                "Google authorization could not be refreshed. A new token.json may be required."
            ) from exc

        token_file.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    if not credentials.valid:
        raise GoogleCalendarAuthenticationError("The Google credentials are invalid.")

    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def list_available_calendars() -> list[dict[str, str]]:
    """
    List Google calendars available to the authorized account.

    Returns:
        Calendar metadata dictionaries with id, summary, and primary fields.
    """
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


def format_available_calendars(calendars: list[dict[str, str]]) -> str:
    """
    Format available calendars for assistant or CLI output.

    Args:
        calendars: Calendar metadata from list_available_calendars().

    Returns:
        Human-readable numbered list of calendars and IDs.
    """
    if not calendars:
        return "No calendars found."

    lines = ["Available calendars:"]
    for index, calendar in enumerate(calendars, start=1):
        label = calendar["summary"]
        if calendar.get("primary") == "true":
            label = f"{label} (primary)"
        lines.append(f"{index}. {label} — id: {calendar['id']}")

    return "\n".join(lines)


def resolve_calendar_ids(calendar_id: str | None = None) -> list[str]:
    """
    Resolve which calendar IDs should be queried.

    Args:
        calendar_id: Optional single calendar override.

    Returns:
        Calendar IDs to query.
    """
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
    """
    Extract a displayable start time from a Calendar API event.

    Args:
        event: Google Calendar event dictionary.

    Returns:
        ISO date/time string or a fallback label.
    """
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
    """
    List Google Calendar events within a date/time range.

    Args:
        calendar_id: Target calendar ID.
        time_min: Inclusive range start.
        time_max: Exclusive range end.

    Returns:
        Normalized event dictionaries for API/UI consumption.

    Raises:
        GoogleCalendarAuthenticationError: When authorization is missing or invalid.
        GoogleCalendarNotFoundError: When the calendar ID is unavailable.
    """
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
    """
    List upcoming events from configured or requested Google calendars.

    Args:
        maximum_results: Maximum number of events to return after merging.
        calendar_id: Optional single-calendar override.

    Returns:
        List of Google Calendar event dictionaries.

    Raises:
        GoogleCalendarAuthenticationError: When authorization is missing or invalid.
        GoogleCalendarNotFoundError: When a requested calendar ID is unavailable.
        HttpError: When the Google Calendar API request fails.
    """
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


def format_upcoming_events(
    events: list[dict[str, Any]],
) -> str:
    """
    Format upcoming calendar events for assistant or CLI output.

    Args:
        events: Google Calendar event dictionaries.

    Returns:
        Human-readable multi-line summary.
    """
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
