from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_FILE_ID_IN_PATH = re.compile(r"/file/d/([a-zA-Z0-9_-]+)")
_FOLDER_IN_PATH = re.compile(r"/drive/folders/([a-zA-Z0-9_-]+)")
_BARE_FILE_ID = re.compile(r"^[a-zA-Z0-9_-]{10,}$")


class GoogleDriveIdError(ValueError):
    pass


def parse_drive_file_id(raw: str) -> str:
    """
    Extract a Google Drive file ID from a bare ID or common share URL.

    Args:
        raw: File ID or Drive URL.

    Returns:
        Normalized file ID.

    Raises:
        GoogleDriveIdError: If the value is empty, a folder URL, or not parseable.
    """
    value = raw.strip()
    if not value:
        raise GoogleDriveIdError("file_id or url is required.")

    if _BARE_FILE_ID.match(value):
        return value

    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise GoogleDriveIdError("Could not parse a Google Drive file ID from that value.")

    path = parsed.path or ""
    if _FOLDER_IN_PATH.search(path):
        raise GoogleDriveIdError("That link looks like a folder. Provide a file link or file ID.")

    path_match = _FILE_ID_IN_PATH.search(path)
    if path_match:
        return path_match.group(1)

    query = parse_qs(parsed.query)
    id_values = query.get("id")
    if id_values and id_values[0].strip():
        return id_values[0].strip()

    open_match = re.search(r"/open\?id=([a-zA-Z0-9_-]+)", value)
    if open_match:
        return open_match.group(1)

    raise GoogleDriveIdError("Could not parse a Google Drive file ID from that URL.")


def _try_parse_drive_file_id(raw: str) -> str | None:
    try:
        return parse_drive_file_id(raw)
    except GoogleDriveIdError:
        return None


def extract_drive_file_reference(message: str) -> str | None:
    """
    Return a Drive file ID if the message starts with a file URL or ID (nano-ui Ask shape).

    Scans the first non-empty line, then the full trimmed message. Returns None for normal chat.
    """
    stripped = message.strip()
    if not stripped:
        return None

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if lines:
        reference = _try_parse_drive_file_id(lines[0])
        if reference is not None:
            return reference

    return _try_parse_drive_file_id(stripped)
