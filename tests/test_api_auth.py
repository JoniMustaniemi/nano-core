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


def test_cors_preflight_for_patch_timer_endpoint(monkeypatch) -> None:
    import importlib

    import app.main as main

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    client = TestClient(main.app)
    response = client.options(
        "/api/timers/1",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "PATCH" in allow_methods.upper()
    get_settings.cache_clear()


def test_patch_timer_returns_cors_headers_on_success(monkeypatch) -> None:
    import importlib
    from datetime import UTC, datetime, timedelta

    import app.main as main
    from app.memory import repository

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    timer = repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    assert timer.id is not None

    client = TestClient(main.app)
    response = client.patch(
        f"/api/timers/{timer.id}",
        json={"label": "Pizza"},
        headers={
            "Origin": "http://localhost:3000",
            "Authorization": "Bearer secret-key",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.json()["label"] == "Pizza"
    get_settings.cache_clear()


def test_patch_timer_returns_cors_headers_on_not_found(monkeypatch) -> None:
    import importlib

    import app.main as main

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    client = TestClient(main.app)
    response = client.patch(
        "/api/timers/99999",
        json={"label": "Pizza"},
        headers={
            "Origin": "http://localhost:3000",
            "Authorization": "Bearer secret-key",
        },
    )

    assert response.status_code == 404
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    get_settings.cache_clear()


def test_cors_preflight_for_delete_timer_endpoint(monkeypatch) -> None:
    import importlib

    import app.main as main

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    client = TestClient(main.app)
    response = client.options(
        "/api/timers/1",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "DELETE" in allow_methods.upper()
    get_settings.cache_clear()


def test_delete_timer_returns_cors_headers_on_success(monkeypatch) -> None:
    import importlib
    from datetime import UTC, datetime, timedelta

    import app.main as main
    from app.memory import repository

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    timer = repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    assert timer.id is not None

    client = TestClient(main.app)
    response = client.delete(
        f"/api/timers/{timer.id}",
        headers={
            "Origin": "http://localhost:3000",
            "Authorization": "Bearer secret-key",
        },
    )

    assert response.status_code == 204
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    get_settings.cache_clear()


def test_delete_timer_returns_cors_headers_on_not_found(monkeypatch) -> None:
    import importlib

    import app.main as main

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    client = TestClient(main.app)
    response = client.delete(
        "/api/timers/99999",
        headers={
            "Origin": "http://localhost:3000",
            "Authorization": "Bearer secret-key",
        },
    )

    assert response.status_code == 404
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    get_settings.cache_clear()


def test_cors_preflight_for_delete_stopwatch_endpoint(monkeypatch) -> None:
    import importlib

    import app.main as main

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    client = TestClient(main.app)
    response = client.options(
        "/api/stopwatches/1",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "DELETE" in allow_methods.upper()
    get_settings.cache_clear()


def test_delete_stopwatch_returns_cors_headers_on_success(monkeypatch) -> None:
    import importlib

    import app.main as main
    from app.memory import repository

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    stopwatch = repository.add_stopwatch("Lap")
    assert stopwatch.id is not None

    client = TestClient(main.app)
    response = client.delete(
        f"/api/stopwatches/{stopwatch.id}",
        headers={
            "Origin": "http://localhost:3000",
            "Authorization": "Bearer secret-key",
        },
    )

    assert response.status_code == 204
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    get_settings.cache_clear()


def test_delete_stopwatch_returns_cors_headers_on_not_found(monkeypatch) -> None:
    import importlib

    import app.main as main

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    client = TestClient(main.app)
    response = client.delete(
        "/api/stopwatches/99999",
        headers={
            "Origin": "http://localhost:3000",
            "Authorization": "Bearer secret-key",
        },
    )

    assert response.status_code == 404
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    get_settings.cache_clear()


def test_cors_preflight_for_protected_endpoint(monkeypatch) -> None:
    import importlib

    import app.main as main

    monkeypatch.setenv("API_KEY", "secret-key")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    get_settings.cache_clear()
    importlib.reload(main)

    client = TestClient(main.app)
    response = client.options(
        "/api/status",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    get_settings.cache_clear()
