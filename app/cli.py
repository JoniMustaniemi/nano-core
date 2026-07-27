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
    Start Nano with default local dev settings.

    This is the setuptools entry point for the ``start-nano`` command. It binds
    to 127.0.0.1:8000 with auto-reload enabled.
    """
    start_dev()


@app.command("start-cmd")
def start_cmd() -> None:
    """Start Nano locally with default dev settings (same as start-nano entry point)."""
    start_dev()


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
    """Start the full app locally."""
    start_dev(host=host, port=port, reload=reload)


def start_dev(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = True,
) -> None:
    """Run the local web app through Uvicorn."""
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["app"] if reload else None,
    )


if __name__ == "__main__":
    app()
