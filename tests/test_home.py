from fastapi.testclient import TestClient

from app.main import app


def test_homepage_shows_standby_ui() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Nano is in standby." in response.text
    assert "Recent activity" in response.text


def test_status_endpoint_starts_in_standby() -> None:
    with TestClient(app) as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "standby"
    assert payload["headline"] == "Nano is in standby."
