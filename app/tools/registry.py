from __future__ import annotations

from importlib import import_module
from pathlib import Path

from app.tools.base import ToolSpec

_REGISTERED_TOOLS: dict[str, ToolSpec] = {}

# Tools owned by multi-turn interaction flows; excluded from planner prompts.
FLOW_OWNED_TOOLS: frozenset[str] = frozenset(
    {
        "add_note",
        "list_notes",
        "start_timer",
        "list_timers",
        "cancel_timers",
    }
)


def register_tool(tool: ToolSpec) -> ToolSpec:
    """
    Register tool.

    Args:
        tool: Tool specification to register.

    Returns:
        ToolSpec result.
    """
    _REGISTERED_TOOLS[tool.name] = tool
    return tool


def get_tool(name: str) -> ToolSpec | None:
    """
    Get tool.

    Args:
        name: Name value.

    Returns:
        Parsed value when available; otherwise None.
    """
    _load_builtin_tool_modules()
    return _REGISTERED_TOOLS.get(name)


def list_tools(*, exclude: frozenset[str] | None = None) -> list[ToolSpec]:
    """
    List tools.

    Args:
        exclude: Optional tool names to omit from the result.

    Returns:
        List of matching records or values.
    """
    _load_builtin_tool_modules()
    excluded = exclude or frozenset()
    return sorted(
        (tool for tool in _REGISTERED_TOOLS.values() if tool.name not in excluded),
        key=lambda tool: tool.name,
    )


def render_tool_prompt(*, exclude: frozenset[str] | None = None) -> str:
    """
    Render tool prompt.

    Args:
        exclude: Optional tool names to omit from the planner prompt.

    Returns:
        Generated or formatted string value.
    """
    lines = ["Available tools:"]
    lines.extend(tool.prompt_line() for tool in list_tools(exclude=exclude))
    lines.append("Return JSON only in one of these forms:")
    lines.append('{"type":"answer_intent"}')
    lines.append('{"type":"tool_call","tool":"tool_name","args":{"key":"value"}}')
    return "\n".join(lines)


def tool_announcement_for(name: str) -> str:
    """
    Return the user-facing announcement for a registered tool.

    Args:
        name: Registered tool name.

    Returns:
        Announcement text or a generic fallback.
    """
    tool = get_tool(name)
    if tool is not None and tool.announcement is not None:
        return tool.announcement
    return "Performing a local action."


def tool_keywords_for(name: str) -> tuple[str, ...]:
    """
    Return keyword hints for a registered tool.

    Args:
        name: Registered tool name.

    Returns:
        Keyword tuple, possibly empty.
    """
    tool = get_tool(name)
    if tool is None:
        return ()
    return tool.keywords


def list_ui_tool_commands() -> list[ToolSpec]:
    """
    Return registered tools that expose web UI quick commands.

    Returns:
        Tool specs with UI metadata, sorted by category then label.
    """
    _load_builtin_tool_modules()
    tools = [tool for tool in _REGISTERED_TOOLS.values() if tool.has_ui_command]
    return sorted(tools, key=lambda tool: (tool.ui_category or "", tool.ui_label or ""))


def _load_builtin_tool_modules() -> None:
    """
    Import built-in tool modules so they can register themselves.

    Returns:
        None.
    """
    if _REGISTERED_TOOLS:
        return

    package_dir = Path(__file__).resolve().parent
    for path in package_dir.glob("*_tools.py"):
        import_module(f"{__package__}.{path.stem}")
