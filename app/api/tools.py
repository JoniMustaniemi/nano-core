from fastapi import APIRouter

from app.web.tool_commands import list_tool_commands

router = APIRouter(tags=["tools"])


@router.get("/tool-commands")
def tool_commands() -> list[dict[str, str]]:
    """Return quick-command buttons for the web UI."""
    return list_tool_commands()
