from typer.testing import CliRunner

from app.cli import app


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
