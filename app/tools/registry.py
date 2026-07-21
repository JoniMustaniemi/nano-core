from __future__ import annotations

from importlib import import_module
from pathlib import Path

from app.tools.base import ToolSpec

_REGISTERED_TOOLS: dict[str, ToolSpec] = {}


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


def list_tools() -> list[ToolSpec]:
    """
    List tools.

    Returns:
        List of matching records or values.
    """
    _load_builtin_tool_modules()
    return sorted(_REGISTERED_TOOLS.values(), key=lambda tool: tool.name)


def render_tool_prompt() -> str:
    """
    Render tool prompt.

    Returns:
        Generated or formatted string value.
    """
    lines = ["Available tools:"]
    lines.extend(tool.prompt_line() for tool in list_tools())
    lines.append("Return JSON only in one of these forms:")
    lines.append('{"type":"answer_intent"}')
    lines.append('{"type":"tool_call","tool":"tool_name","args":{"key":"value"}}')
    return "\n".join(lines)


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
