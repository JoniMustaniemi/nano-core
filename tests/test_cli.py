from typer.testing import CliRunner

from app.cli import app, start


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
    """
    Verify that start entrypoint launches uvicorn with defaults.

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

    start()

    assert calls == [
        (
            ("app.main:app",),
            {"host": "127.0.0.1", "port": 8000, "reload": True, "reload_dirs": ["app"]},
        )
    ]


def test_start_cmd_command_launches_uvicorn_with_defaults(monkeypatch) -> None:
    """
    Verify that start-cmd Typer command launches uvicorn with defaults.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
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
            {"host": "127.0.0.1", "port": 8000, "reload": True, "reload_dirs": ["app"]},
        )
    ]
