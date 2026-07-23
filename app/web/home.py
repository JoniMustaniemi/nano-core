from html import escape
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.web.tool_commands import list_tool_commands

router = APIRouter(tags=["web"])

_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "home.html"


@router.get("/api/tool-commands")
def tool_commands() -> list[dict[str, str]]:
    """
    Return quick-command buttons for the web UI.

    Returns:
        Tool command definitions.
    """
    return list_tool_commands()


@router.get("/", response_class=HTMLResponse)
def home() -> str:
    """
    Render the home page.

    Returns:
        Generated or formatted string value.
    """
    settings = get_settings()
    app_name = escape(settings.app_name)
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("{app_name}", app_name)
