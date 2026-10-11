from __future__ import annotations

from pathlib import Path
from typing import cast

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import get_settings

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_AUTH_COMMAND = "`nano-core auth-google` or `nano-core auth-google-calendar`"


class GoogleAuthenticationError(RuntimeError):
    pass


def _credentials_path() -> Path:
    return Path(get_settings().google_credentials_path)


def _token_path() -> Path:
    return Path(get_settings().google_token_path)


def run_authorization_flow() -> Path:
    credentials_file = _credentials_path()
    token_file = _token_path()

    if not credentials_file.exists():
        raise FileNotFoundError(f"Missing file: {credentials_file}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        scopes=GOOGLE_SCOPES,
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


def get_credentials() -> Credentials:
    token_file = _token_path()

    if not token_file.exists():
        raise GoogleAuthenticationError(
            "token.json is missing. Run "
            f"{_AUTH_COMMAND} or `python scripts/google_calendar_auth.py` to authorize."
        )

    try:
        credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(token_file),
            GOOGLE_SCOPES,
        )
    except (OSError, ValueError) as exc:
        raise GoogleAuthenticationError(f"Could not read token.json: {exc}") from exc

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as exc:
            raise GoogleAuthenticationError(
                "Google authorization could not be refreshed. A new token.json may be required."
            ) from exc

        token_file.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    if not credentials.valid:
        raise GoogleAuthenticationError("The Google credentials are invalid.")

    return cast(Credentials, credentials)
