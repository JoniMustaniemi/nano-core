import os
from datetime import datetime

import typer
import uvicorn

from app.assistant.service import AssistantService
from app.config import get_settings
from app.memory.repository import add_note, add_reminder, list_notes, list_reminders

app = typer.Typer(help="Nano Core local assistant CLI.")
notes_app = typer.Typer(help="Manage notes.")
reminders_app = typer.Typer(help="Manage reminders.")

app.add_typer(notes_app, name="notes")
app.add_typer(reminders_app, name="reminders")


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


@app.command()
def chat(
    message: str,
    mode: str = typer.Option("agent", "--mode", help="Use chat or agent mode."),
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
    if reload:
        os.environ["NANO_UVICORN_RELOAD"] = "1"
    else:
        os.environ.pop("NANO_UVICORN_RELOAD", None)
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["app"] if reload else None,
    )


@notes_app.command("add")
def note_add(
    content: str = typer.Argument(..., help="Note text to store."),
    name: str = typer.Option("Untitled note", "--name", "-n", help="Name for the note."),
) -> None:
    """Store a note in the local database."""
    note = add_note(content, name=name)
    typer.echo(f"saved note {note.id} ({note.name}): {note.content}")


@notes_app.command("list")
def note_list() -> None:
    """List notes from the local database."""
    for note in list_notes():
        typer.echo(f"{note.id}: {note.name} - {note.content}")


@reminders_app.command("add")
def reminder_add(
    content: str = typer.Argument(..., help="Reminder text to store."),
    due_at: str = typer.Argument(..., help="Due time in ISO 8601 format."),
) -> None:
    """Store a reminder in the local database."""
    reminder_due_at = datetime.fromisoformat(due_at)
    reminder = add_reminder(content, reminder_due_at)
    typer.echo(f"saved reminder {reminder.id}: {reminder.content}")


@reminders_app.command("list")
def reminder_list() -> None:
    """List reminders from the local database."""
    for reminder in list_reminders():
        typer.echo(f"{reminder.id}: {reminder.content} @ {reminder.due_at.isoformat()}")


if __name__ == "__main__":
    app()
