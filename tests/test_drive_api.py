from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.integrations.google_drive import GoogleDriveAuthenticationError
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_read_drive_file_metadata(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.drive.get_file_metadata",
        lambda _file_id: {
            "id": "abc",
            "name": "Notes",
            "mimeType": "text/plain",
            "size": 10,
        },
    )

    response = client.get("/api/drive/files/abc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Notes"
    assert payload["mime_type"] == "text/plain"


def test_read_drive_file_metadata_auth_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_auth(_file_id: str) -> dict[str, object]:
        raise GoogleDriveAuthenticationError("token.json is missing.")

    monkeypatch.setattr("app.api.drive.get_file_metadata", raise_auth)

    response = client.get("/api/drive/files/abc")
    assert response.status_code == 503
    assert "token.json is missing" in response.json()["detail"]
