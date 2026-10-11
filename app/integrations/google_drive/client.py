from __future__ import annotations

import io
from typing import Any

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from app.config import get_settings
from app.integrations.google_drive.auth import get_drive_service

MIME_GOOGLE_DOC = "application/vnd.google-apps.document"
MIME_GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
MIME_GOOGLE_SLIDE = "application/vnd.google-apps.presentation"

_EXPORT_MIME: dict[str, str] = {
    MIME_GOOGLE_DOC: "text/plain",
    MIME_GOOGLE_SHEET: "text/csv",
    MIME_GOOGLE_SLIDE: "text/plain",
}

_TEXTUAL_MIME_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
)


class GoogleDriveNotFoundError(RuntimeError):
    pass


class GoogleDriveAccessError(RuntimeError):
    pass


class GoogleDriveBinaryNotSupportedError(RuntimeError):
    pass


def _max_export_bytes() -> int:
    return get_settings().google_drive_max_export_bytes


def _truncate_bytes(data: bytes, limit: int) -> tuple[bytes, bool]:
    if len(data) <= limit:
        return data, False
    return data[:limit], True


def _decode_text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _is_textual_mime(mime_type: str) -> bool:
    if mime_type in _EXPORT_MIME.values():
        return True
    return any(mime_type.startswith(prefix) for prefix in _TEXTUAL_MIME_PREFIXES)


def get_file_metadata(file_id: str) -> dict[str, str | int | None]:
    service = get_drive_service()
    try:
        result = (
            service.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,size",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        _raise_for_http_error(exc)

    if not isinstance(result, dict):
        raise GoogleDriveAccessError("Unexpected response from Google Drive.")

    size_raw = result.get("size")
    size: int | None
    if isinstance(size_raw, str) and size_raw.isdigit():
        size = int(size_raw)
    elif isinstance(size_raw, int):
        size = size_raw
    else:
        size = None

    return {
        "id": str(result.get("id") or file_id),
        "name": str(result.get("name") or ""),
        "mimeType": str(result.get("mimeType") or ""),
        "size": size,
    }


def read_file_content(file_id: str) -> tuple[str, str, bool]:
    """
    Read file content as text for LLM or API consumers.

    Returns:
        Tuple of (file name, text content, truncated flag).
    """
    metadata = get_file_metadata(file_id)
    name = str(metadata.get("name") or file_id)
    mime_type = str(metadata.get("mimeType") or "")
    limit = _max_export_bytes()

    export_mime = _EXPORT_MIME.get(mime_type)
    if export_mime is not None:
        data, truncated = _download_export(file_id, export_mime, limit)
        return name, _decode_text(data), truncated

    if not _is_textual_mime(mime_type):
        raise GoogleDriveBinaryNotSupportedError(
            f"File '{name}' has type {mime_type or 'unknown'}; only text-like files are supported."
        )

    data, truncated = _download_media(file_id, limit)
    return name, _decode_text(data), truncated


def _download_export(file_id: str, export_mime: str, limit: int) -> tuple[bytes, bool]:
    service = get_drive_service()
    try:
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        return _download_request(request, limit)
    except HttpError as exc:
        _raise_for_http_error(exc)
        raise


def _download_media(file_id: str, limit: int) -> tuple[bytes, bool]:
    service = get_drive_service()
    try:
        request = service.files().get_media(fileId=file_id)
        return _download_request(request, limit)
    except HttpError as exc:
        _raise_for_http_error(exc)
        raise


def _download_request(request: Any, limit: int) -> tuple[bytes, bool]:
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
        if buffer.tell() > limit:
            data, truncated = _truncate_bytes(buffer.getvalue(), limit)
            return data, True
    data, truncated = _truncate_bytes(buffer.getvalue(), limit)
    return data, truncated


def _raise_for_http_error(exc: HttpError) -> None:
    status = exc.resp.status if exc.resp else None
    if status == 404:
        raise GoogleDriveNotFoundError("That Google Drive file was not found.") from exc
    if status in (403, 401):
        raise GoogleDriveAccessError(
            "Google Drive denied access to that file. Check sharing and authorization."
        ) from exc
    raise GoogleDriveAccessError(f"Google Drive API request failed: {exc}") from exc
