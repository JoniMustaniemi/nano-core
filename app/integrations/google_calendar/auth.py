from __future__ import annotations

from pathlib import Path

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
    raw = get_settings().google_calendar_ids.strip()
    if not raw:
        return ["primary"]
    return [part.strip() for part in raw.split(",") if part.strip()]


def run_authorization_flow() -> Path:
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
