import typer

from app.assistant.service import AssistantService
from app.config import get_settings

app = typer.Typer(help="Nano Core local assistant CLI.")


@app.command()
def health() -> None:
    """Print basic app health information."""
    settings = get_settings()
    typer.echo(f"{settings.app_name} is configured for {settings.app_env}.")


@app.command()
def chat(message: str) -> None:
    """Send a message to the assistant."""
    response = AssistantService().respond(message)
    typer.echo(response.content)


if __name__ == "__main__":
    app()
