from datetime import UTC, datetime, timedelta
from pathlib import Path

from googleapiclient.errors import HttpError
from typer.testing import CliRunner

from app.cli import app, start
from app.integrations.google_calendar import GoogleCalendarAuthenticationError


def test_dev_command_launches_uvicorn(monkeypatch) -> None:
    """
    Verify that dev command launches uvicorn.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        """
        Provide a fake run implementation for the test.

        Args:
            args: Tool argument dictionary.
            kwargs: Kwargs value.

        Returns:
            None.
        """
        calls.append((args, kwargs))

    monkeypatch.setattr("app.cli.uvicorn.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(app, ["dev", "--host", "127.0.0.1", "--port", "9000", "--no-reload"])

    assert result.exit_code == 0
    assert calls == [
        (
            ("app.main:app",),
            {"host": "127.0.0.1", "port": 9000, "reload": False, "reload_dirs": None},
        )
    ]


def test_start_entrypoint_launches_uvicorn_with_defaults(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        """
        Provide a fake run implementation for the test.

        Args:
            args: Tool argument dictionary.
            kwargs: Kwargs value.

        Returns:
            None.
        """
        calls.append((args, kwargs))

    monkeypatch.setattr("app.cli.uvicorn.run", fake_run)

    start()

    assert calls == [
        (
            ("app.main:app",),
            {"host": "0.0.0.0", "port": 8000, "reload": False, "reload_dirs": None},
        )
    ]


def test_start_cmd_command_launches_uvicorn_with_defaults(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("app.cli.uvicorn.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(app, ["start-cmd"])

    assert result.exit_code == 0
    assert calls == [
        (
            ("app.main:app",),
            {"host": "0.0.0.0", "port": 8000, "reload": False, "reload_dirs": None},
        )
    ]


def test_serve_command_uses_bind_settings(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("app.cli.uvicorn.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--host", "10.0.0.5", "--port", "9001"])

    assert result.exit_code == 0
    assert calls == [
        (
            ("app.main:app",),
            {"host": "10.0.0.5", "port": 9001, "reload": False, "reload_dirs": None},
        )
    ]


def test_auth_google_calendar_command_writes_token(monkeypatch) -> None:
    token_path = "token.json"

    monkeypatch.setattr(
        "app.cli.run_authorization_flow",
        lambda: __import__("pathlib").Path(token_path),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["auth-google-calendar"])

    assert result.exit_code == 0
    assert token_path in result.output


def test_auth_google_calendar_command_missing_credentials(monkeypatch) -> None:
    def raise_missing() -> None:
        raise FileNotFoundError("Missing file: credentials.json")

    monkeypatch.setattr("app.cli.run_authorization_flow", raise_missing)

    runner = CliRunner()
    result = runner.invoke(app, ["auth-google-calendar"])

    assert result.exit_code == 1
    assert "Missing file: credentials.json" in result.output


def test_google_calendars_command_prints_calendars(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.cli.list_available_calendars",
        lambda: [{"id": "primary", "summary": "Personal", "primary": "true"}],
    )

    runner = CliRunner()
    result = runner.invoke(app, ["google-calendars"])

    assert result.exit_code == 0
    assert "Available calendars:" in result.output
    assert "Personal (primary) — id: primary" in result.output


def test_google_calendars_command_exits_on_auth_error(monkeypatch) -> None:
    def raise_auth_error() -> list[dict[str, str]]:
        raise GoogleCalendarAuthenticationError("token.json is missing.")

    monkeypatch.setattr("app.cli.list_available_calendars", raise_auth_error)

    runner = CliRunner()
    result = runner.invoke(app, ["google-calendars"])

    assert result.exit_code == 1
    assert "token.json is missing." in result.output


def test_google_calendars_command_exits_on_http_error(monkeypatch) -> None:
    from unittest.mock import MagicMock

    response = MagicMock(status=403)
    error = HttpError(response, b"forbidden")

    def raise_http_error() -> list[dict[str, str]]:
        raise error

    monkeypatch.setattr("app.cli.list_available_calendars", raise_http_error)

    runner = CliRunner()
    result = runner.invoke(app, ["google-calendars"])

    assert result.exit_code == 1
    assert "Google Calendar API request failed:" in result.output


def test_clear_all_timers_command_removes_active_timers() -> None:
    from app.memory import repository

    repository.add_timer("Tea", datetime.now(UTC) + timedelta(minutes=5))
    repository.add_stopwatch("Lap")

    runner = CliRunner()
    result = runner.invoke(app, ["clear-all-timers"])

    assert result.exit_code == 0
    assert "Cleared 1 countdown timer and 1 stopwatch." in result.output
    assert repository.list_timers() == []


def test_serve_runs_auto_update_when_enabled(monkeypatch) -> None:
    from app.config import get_settings
    from app.deploy.update import PullResult

    pull_calls: list[Path | None] = []

    def fake_pull(repo_root: Path | None = None) -> PullResult:
        pull_calls.append(repo_root)
        return PullResult(updated=False, message="Already up to date.")

    monkeypatch.setenv("AUTO_UPDATE_ON_START", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.deploy.update.pull_latest", fake_pull)
    monkeypatch.setattr("app.cli.uvicorn.run", lambda *args, **kwargs: None)

    runner = CliRunner()
    result = runner.invoke(app, ["serve"])

    assert result.exit_code == 0
    assert pull_calls == [None]
    assert "Auto-update: Already up to date." in result.output
    get_settings.cache_clear()
