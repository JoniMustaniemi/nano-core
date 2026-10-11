from __future__ import annotations

from googleapiclient.discovery import Resource, build

from app.config import get_settings
from app.integrations.google.auth import (
    GoogleAuthenticationError,
    get_credentials,
    run_authorization_flow,
)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class GoogleCalendarAuthenticationError(GoogleAuthenticationError):
    pass


class GoogleCalendarNotFoundError(RuntimeError):
    pass


def configured_calendar_ids() -> list[str]:
    raw = get_settings().google_calendar_ids.strip()
    if not raw:
        return ["primary"]
    return [part.strip() for part in raw.split(",") if part.strip()]


def get_calendar_service() -> Resource:
    try:
        credentials = get_credentials()
    except GoogleAuthenticationError as exc:
        raise GoogleCalendarAuthenticationError(str(exc)) from exc

    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


__all__ = [
    "GoogleCalendarAuthenticationError",
    "GoogleCalendarNotFoundError",
    "SCOPES",
    "configured_calendar_ids",
    "get_calendar_service",
    "run_authorization_flow",
]
