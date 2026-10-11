from __future__ import annotations

from typing import Any

from googleapiclient.errors import HttpError

from app.integrations.google_drive import (
    GoogleDriveAccessError,
    GoogleDriveAuthenticationError,
    GoogleDriveBinaryNotSupportedError,
    GoogleDriveIdError,
    GoogleDriveNotFoundError,
    format_file_content,
    parse_drive_file_id,
    read_file_content,
)
from app.tools.base import ToolSpec
from app.tools.registry import register_tool


def _resolve_file_id(args: dict[str, Any]) -> str:
    file_id = args.get("file_id")
    url = args.get("url")
    if isinstance(file_id, str) and file_id.strip():
        return parse_drive_file_id(file_id.strip())
    if isinstance(url, str) and url.strip():
        return parse_drive_file_id(url.strip())
    raise ValueError("Provide file_id or url.")


def _read_google_drive_file(args: dict[str, Any]) -> str:
    """
    Read a Google Drive file by ID or share URL (read-only).

    Args:
        args: file_id or url.

    Returns:
        File name and text content for the model.
    """
    try:
        resolved_id = _resolve_file_id(args)
    except (ValueError, GoogleDriveIdError) as exc:
        return str(exc)

    try:
        name, content, truncated = read_file_content(resolved_id)
    except GoogleDriveAuthenticationError as exc:
        return str(exc)
    except GoogleDriveNotFoundError as exc:
        return str(exc)
    except GoogleDriveAccessError as exc:
        return str(exc)
    except GoogleDriveBinaryNotSupportedError as exc:
        return str(exc)
    except HttpError as exc:
        return f"Google Drive API request failed: {exc}"

    return format_file_content(name, content, truncated=truncated)


register_tool(
    ToolSpec(
        name="read_google_drive_file",
        description=(
            "Read a Google Drive file as text by file ID or share URL. "
            "Read-only; requires Google authorization. "
            "Does not search Drive — the user must supply the link or ID. "
            "When the message starts with a Drive URL or ID on its own line followed by a question, "
            "pass that full URL or ID string as url or file_id, then answer from the file content."
        ),
        args_schema={
            "file_id": "optional Drive file ID (or paste a file URL here)",
            "url": "optional Google Drive file URL",
        },
        handler=_read_google_drive_file,
        announcement="Reading from Google Drive.",
        keywords=(
            "google drive",
            "drive",
            "google doc",
            "google sheet",
            "spreadsheet",
            "gdrive",
        ),
    )
)
