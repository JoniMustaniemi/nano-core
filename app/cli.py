from typing import Literal

import typer
import uvicorn
from googleapiclient.errors import HttpError

from app.assistant.service import AssistantService
from app.config import get_settings
from app.integrations.google_calendar import (
    GoogleCalendarAuthenticationError,
    format_available_calendars,
    list_available_calendars,
    run_authorization_flow,
)

app = typer.Typer(help="Nano Core local assistant CLI.")


def start() -> None:
    """
    Start Nano in production API mode.

    This is the setuptools entry point for the ``start-nano`` command.
    """
    _run_serve()


@app.command("start-cmd")
def start_cmd() -> None:
    """Start Nano in production API mode (same as start-nano entry point)."""
    _run_serve()


@app.command()
def health() -> None:
    """Print basic app health information."""
    settings = get_settings()
    typer.echo(f"{settings.app_name} is configured for {settings.app_env}.")


@app.command("auth-google-calendar")
def auth_google_calendar() -> None:
    """Run one-time Google Calendar OAuth and save token.json."""
    try:
        token_file = run_authorization_flow()
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Created {token_file.resolve()}")


@app.command("google-calendars")
def google_calendars() -> None:
    """List available Google calendars and their IDs."""
    try:
        calendars = list_available_calendars()
    except GoogleCalendarAuthenticationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except HttpError as exc:
        typer.echo(f"Google Calendar API request failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(format_available_calendars(calendars))


@app.command()
def chat(
    message: str,
    mode: Literal["chat", "agent"] = typer.Option(
        "agent", "--mode", help="Use chat or agent mode."
    ),
) -> None:
    """Send a message to the assistant."""
    response = AssistantService().respond(message, mode=mode)
    typer.echo(response.content)


@app.command()
def dev(
    host: str = typer.Option("127.0.0.1", help="Host to bind."),
    port: int = typer.Option(8000, help="Port to bind."),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Enable auto-reload."),
) -> None:
    """Start the API locally for development."""
    start_dev(host=host, port=port, reload=reload)


@app.command()
def serve(
    host: str | None = typer.Option(None, help="Override API_BIND_HOST."),
    port: int | None = typer.Option(None, help="Override API_BIND_PORT."),
) -> None:
    """Start the API-only server for remote UI clients."""
    _run_serve(host=host, port=port)


def _run_serve(host: str | None = None, port: int | None = None) -> None:
    settings = get_settings()
    if settings.auto_update_on_start:
        from app.deploy.update import install_dependencies, pull_latest

        result = pull_latest()
        typer.echo(f"Auto-update: {result.message}")
        if result.updated and settings.auto_update_install:
            if install_dependencies():
                typer.echo("Auto-update: dependencies reinstalled.")
            else:
                typer.echo("Auto-update: dependency reinstall failed; continuing with local install.")

    resolved_host = host or settings.api_bind_host
    resolved_port = port or settings.api_bind_port
    if settings.api_key.strip():
        typer.echo(f"API key authentication is enabled on {resolved_host}:{resolved_port}.")
    else:
        typer.echo("Warning: API_KEY is not set. Configure one before exposing this server.")
    start_dev(host=resolved_host, port=resolved_port, reload=False)


def start_dev(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = True,
) -> None:
    """Run the API through Uvicorn."""
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["app"] if reload else None,
    )


if __name__ == "__main__":
    app()
