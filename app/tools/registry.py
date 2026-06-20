from __future__ import annotations

from importlib import import_module
from pathlib import Path

from app.tools.base import ToolSpec

_REGISTERED_TOOLS: dict[str, ToolSpec] = {}


def register_tool(tool: ToolSpec) -> ToolSpec:
    _REGISTERED_TOOLS[tool.name] = tool
    return tool


def get_tool(name: str) -> ToolSpec | None:
    _load_builtin_tool_modules()
    return _REGISTERED_TOOLS.get(name)


def list_tools() -> list[ToolSpec]:
    _load_builtin_tool_modules()
    return sorted(_REGISTERED_TOOLS.values(), key=lambda tool: tool.name)


def render_tool_prompt() -> str:
    lines = ["Available tools:"]
    lines.extend(tool.prompt_line() for tool in list_tools())
    lines.append("Return JSON only in one of these forms:")
    lines.append('{"type":"final","content":"..."}')
    lines.append('{"type":"tool_call","tool":"tool_name","args":{"key":"value"}}')
    return "\n".join(lines)


def _load_builtin_tool_modules() -> None:
    if _REGISTERED_TOOLS:
        return

    package_dir = Path(__file__).resolve().parent
    for path in package_dir.glob("*_tools.py"):
        import_module(f"{__package__}.{path.stem}")
