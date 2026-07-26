from html import escape
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

from app.config import get_settings

router = APIRouter(tags=["web"])

_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "home.html"
_FAVICON_PATH = Path(__file__).resolve().parent / "static" / "favicon.svg"


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    """Serve the site favicon for browsers that request /favicon.ico directly."""
    return FileResponse(_FAVICON_PATH, media_type="image/svg+xml")


@router.get("/", response_class=HTMLResponse)
def home() -> str:
    """Render the home page."""
    settings = get_settings()
    app_name = escape(settings.app_name)
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.replace("{app_name}", app_name)
