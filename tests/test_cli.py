from typer.testing import CliRunner

from app.cli import app, start


def test_dev_command_launches_uvicorn(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("app.cli.uvicorn.run", fake_run)

    runner = CliRunner()
    result = runner.invoke(app, ["dev", "--host", "0.0.0.0", "--port", "9000", "--no-reload"])

    assert result.exit_code == 0
    assert calls == [
        (
            ("app.main:app",),
            {"host": "0.0.0.0", "port": 9000, "reload": False},
        )
    ]


def test_start_entrypoint_launches_uvicorn_with_defaults(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("app.cli.uvicorn.run", fake_run)

    start()

    assert calls == [
        (
            ("app.main:app",),
            {"host": "127.0.0.1", "port": 8000, "reload": True},
        )
    ]
