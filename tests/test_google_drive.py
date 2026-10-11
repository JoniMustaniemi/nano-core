from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from app.integrations.google_drive import (
    GoogleDriveAuthenticationError,
    GoogleDriveBinaryNotSupportedError,
    GoogleDriveIdError,
    GoogleDriveNotFoundError,
    extract_drive_file_reference,
    format_file_content,
    format_file_metadata,
    parse_drive_file_id,
    read_file_content,
)
from app.tools import get_tool


def test_parse_drive_file_id_accepts_bare_id() -> None:
    file_id = "1a2b3c4d5e6f7g8h9i0j"
    assert parse_drive_file_id(file_id) == file_id


def test_parse_drive_file_id_from_file_url() -> None:
    url = "https://drive.google.com/file/d/abc123XYZ/view?usp=sharing"
    assert parse_drive_file_id(url) == "abc123XYZ"


def test_parse_drive_file_id_from_open_url() -> None:
    url = "https://drive.google.com/open?id=openId123456"
    assert parse_drive_file_id(url) == "openId123456"


def test_parse_drive_file_id_rejects_folder_url() -> None:
    url = "https://drive.google.com/drive/folders/folderId123"
    with pytest.raises(GoogleDriveIdError, match="folder"):
        parse_drive_file_id(url)


def test_extract_drive_file_reference_from_url_and_finnish_question() -> None:
    message = "https://drive.google.com/file/d/abc123XYZ/view?usp=sharing\n\nMitä tässä sanotaan?"
    assert extract_drive_file_reference(message) == "abc123XYZ"


def test_extract_drive_file_reference_from_bare_id_first_line() -> None:
    file_id = "abcdefghijklmnop"
    message = f"{file_id}\n\nMitä tässä sanotaan?"
    assert extract_drive_file_reference(message) == file_id


def test_extract_drive_file_reference_ignores_folder_first_line() -> None:
    message = "https://drive.google.com/drive/folders/folderId123\n\nMitä tässä sanotaan?"
    assert extract_drive_file_reference(message) is None


def test_extract_drive_file_reference_question_only() -> None:
    assert extract_drive_file_reference("Mitä tässä sanotaan?") is None


def test_format_file_metadata() -> None:
    result = format_file_metadata(
        {"id": "abc", "name": "Notes", "mimeType": "text/plain", "size": 42}
    )
    assert "Notes" in result
    assert "text/plain" in result
    assert "42 bytes" in result


def test_format_file_content_truncated() -> None:
    result = format_file_content("Doc", "hello", truncated=True)
    assert "(truncated)" in result
    assert "Doc" in result


def test_read_file_content_exports_google_doc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MagicMock()
    service.files().get().execute.return_value = {
        "id": "doc1",
        "name": "My Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    monkeypatch.setattr(
        "app.integrations.google_drive.client.get_drive_service",
        lambda: service,
    )
    monkeypatch.setattr(
        "app.integrations.google_drive.client._download_export",
        lambda _file_id, _mime, _limit: (b"exported text", False),
    )

    name, content, truncated = read_file_content("doc1")
    assert name == "My Doc"
    assert content == "exported text"
    assert truncated is False


def test_read_file_content_truncates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MagicMock()
    service.files().get().execute.return_value = {
        "id": "doc1",
        "name": "My Doc",
        "mimeType": "application/vnd.google-apps.document",
    }
    monkeypatch.setattr(
        "app.integrations.google_drive.client.get_drive_service",
        lambda: service,
    )
    monkeypatch.setattr(
        "app.integrations.google_drive.client._download_export",
        lambda _file_id, _mime, _limit: (b"abcdef", True),
    )

    _, content, truncated = read_file_content("doc1")
    assert truncated is True
    assert content == "abcdef"


def test_read_file_content_binary_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MagicMock()
    service.files().get().execute.return_value = {
        "id": "bin1",
        "name": "photo.png",
        "mimeType": "image/png",
        "size": "100",
    }
    monkeypatch.setattr(
        "app.integrations.google_drive.client.get_drive_service",
        lambda: service,
    )

    with pytest.raises(GoogleDriveBinaryNotSupportedError):
        read_file_content("bin1")


def test_get_file_metadata_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock(status=404)

    def raise_http(*_args: object, **_kwargs: object) -> None:
        raise HttpError(response, b"not found")

    service = MagicMock()
    service.files().get().execute.side_effect = raise_http
    monkeypatch.setattr(
        "app.integrations.google_drive.client.get_drive_service",
        lambda: service,
    )

    with pytest.raises(GoogleDriveNotFoundError):
        from app.integrations.google_drive import get_file_metadata

        get_file_metadata("missing")


def test_read_google_drive_file_tool_registered() -> None:
    tool = get_tool("read_google_drive_file")
    assert tool is not None
    assert tool.name == "read_google_drive_file"


def test_read_google_drive_file_tool_requires_id_or_url() -> None:
    tool = get_tool("read_google_drive_file")
    assert tool is not None
    result = tool.handler({})
    assert "file_id or url" in result.lower()


def test_read_google_drive_file_tool_auth_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = get_tool("read_google_drive_file")
    assert tool is not None

    def raise_auth(_file_id: str) -> tuple[str, str, bool]:
        raise GoogleDriveAuthenticationError("token.json is missing.")

    monkeypatch.setattr("app.tools.drive_tools.read_file_content", raise_auth)

    result = tool.handler({"file_id": "abc1234567890"})
    assert result == "token.json is missing."
