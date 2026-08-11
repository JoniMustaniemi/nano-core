from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_health_endpoint_is_public_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "secret-key")
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    get_settings.cache_clear()


def test_protected_endpoint_requires_api_key_in_production(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.get("/api/status")

    assert response.status_code == 401
    get_settings.cache_clear()


def test_protected_endpoint_accepts_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.get("/api/status", headers={"Authorization": "Bearer secret-key"})

    assert response.status_code == 200
    get_settings.cache_clear()


def test_events_endpoint_rejects_missing_api_key(monkeypatch) -> None:
    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    client = TestClient(app)
    response = client.get("/api/events?since=0")

    assert response.status_code == 401
    get_settings.cache_clear()
