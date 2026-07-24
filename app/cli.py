import os

import typer
import uvicorn

from app.assistant.service import AssistantService
from app.config import get_settings

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


if __name__ == "__main__":
    app()
