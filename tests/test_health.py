from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.health.checks import HealthCheckResult, run_health_checks
from app.main import app
from app.scheduler import jobs


def test_health_endpoint_reports_checks(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.health.get_settings",
        lambda: SimpleNamespace(app_name="Nano Core", app_env="test"),
    )
    monkeypatch.setattr(
        "app.api.health.run_health_checks",
        lambda: [
            HealthCheckResult(name="database", ok=True, detail="Database is reachable."),
            HealthCheckResult(name="voice", ok=True, detail="Voice is ready."),
        ],
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"][0]["name"] == "database"


def test_health_scheduler_announces_new_failures(monkeypatch) -> None:
    spoken: list[str] = []
    jobs._LAST_HEALTH_STATUS.clear()
    monkeypatch.setattr(
        "app.scheduler.jobs.run_health_checks",
        lambda: [HealthCheckResult(name="voice", ok=False, detail="Voice backend is unavailable.")],
    )
    monkeypatch.setattr(
        "app.scheduler.jobs.GladosVoiceService.announce",
        lambda self, text: spoken.append(text),
    )

    results = jobs.check_system_health()

    assert results[0].ok is False
    assert spoken == ["I detected a problem with voice. Voice backend is unavailable."]


def test_health_scheduler_does_not_repeat_same_failure_announcement(monkeypatch) -> None:
    spoken: list[str] = []
    jobs._LAST_HEALTH_STATUS.clear()
    jobs._LAST_HEALTH_STATUS["voice"] = False
    monkeypatch.setattr(
        "app.scheduler.jobs.run_health_checks",
        lambda: [HealthCheckResult(name="voice", ok=False, detail="Voice backend is unavailable.")],
    )
    monkeypatch.setattr(
        "app.scheduler.jobs.GladosVoiceService.announce",
        lambda self, text: spoken.append(text),
    )

    jobs.check_system_health()

    assert spoken == []


def test_database_size_health_check_warns_when_threshold_is_exceeded(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "nano.sqlite3"
    db_file.write_bytes(b"x" * 2048)
    monkeypatch.setattr("app.health.checks.db.sqlite_path", db_file)
    monkeypatch.setattr(
        "app.health.checks.get_settings",
        lambda: SimpleNamespace(
            database_size_warning_bytes=1024,
            llm_provider="local",
            llm_model_path="model.gguf",
            llm_base_url="",
        ),
    )
    monkeypatch.setattr(
        "app.health.checks.GladosVoiceService.status",
        lambda self: {"available": True, "detail": "Voice is ready."},
    )

    results = run_health_checks()
    size_result = next(result for result in results if result.name == "database_size")

    assert size_result.ok is False
    assert "exceeds the warning threshold" in size_result.detail


def test_database_size_health_check_reports_when_below_threshold(
    monkeypatch,
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "nano.sqlite3"
    db_file.write_bytes(b"x" * 2048)
    monkeypatch.setattr("app.health.checks.db.sqlite_path", db_file)
    monkeypatch.setattr(
        "app.health.checks.get_settings",
        lambda: SimpleNamespace(
            database_size_warning_bytes=10_000,
            llm_provider="local",
            llm_model_path="model.gguf",
            llm_base_url="",
        ),
    )
    monkeypatch.setattr(
        "app.health.checks.GladosVoiceService.status",
        lambda self: {"available": True, "detail": "Voice is ready."},
    )

    results = run_health_checks()
    size_result = next(result for result in results if result.name == "database_size")

    assert size_result.ok is True
    assert "below the warning threshold" in size_result.detail


def test_health_scheduler_announces_database_size_warning(monkeypatch) -> None:
    spoken: list[str] = []
    jobs._LAST_HEALTH_STATUS.clear()
    monkeypatch.setattr(
        "app.scheduler.jobs.run_health_checks",
        lambda: [
            HealthCheckResult(
                name="database_size",
                ok=False,
                detail="Database size is 60.0 MB, which exceeds the warning threshold of 50.0 MB.",
            )
        ],
    )
    monkeypatch.setattr(
        "app.scheduler.jobs.GladosVoiceService.announce",
        lambda self, text: spoken.append(text),
    )

    jobs.check_system_health()

    assert spoken == [
        "I detected a problem with database_size. Database size is 60.0 MB, "
        "which exceeds the warning threshold of 50.0 MB."
    ]
