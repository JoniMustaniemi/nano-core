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
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


@notes_app.command("add")
def note_add(content: str) -> None:
    """Store a note in the local database."""
    note = add_note(content)
    typer.echo(f"saved note {note.id}: {note.content}")


@notes_app.command("list")
def note_list() -> None:
    """List notes from the local database."""
    for note in list_notes():
        typer.echo(f"{note.id}: {note.content}")


@reminders_app.command("add")
def reminder_add(content: str, due_at: str) -> None:
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
