from __future__ import annotations

from googleapiclient.discovery import Resource, build

from app.integrations.google.auth import GoogleAuthenticationError, get_credentials


class GoogleDriveAuthenticationError(GoogleAuthenticationError):
    pass


def get_drive_service() -> Resource:
    try:
        credentials = get_credentials()
    except GoogleAuthenticationError as exc:
        raise GoogleDriveAuthenticationError(str(exc)) from exc

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )
