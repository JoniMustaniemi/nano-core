from __future__ import annotations

from dataclasses import dataclass

from app.tools.registry import tool_announcement_for


@dataclass(frozen=True, slots=True)
class ToolIntentRule:
    announcement: str
    keywords: tuple[str, ...] = ()


def build_tool_rules() -> dict[str, ToolIntentRule]:
    """
    Build tool intent rules from the registered tool catalog.

    Returns:
        Mapping of tool name to intent metadata.
    """
    from app.tools.registry import list_tools

    rules: dict[str, ToolIntentRule] = {}
    for tool in list_tools():
        announcement = tool.announcement or tool_announcement_for(tool.name)
        rules[tool.name] = ToolIntentRule(
            announcement=announcement,
            keywords=tool.keywords,
        )
    return rules


def tool_announcement(tool_name: str) -> str:
    """
    Build tool metadata for announcement.

    Args:
        tool_name: Registered tool name.

    Returns:
        Generated or formatted string value.
    """
    return tool_announcement_for(tool_name)


def tool_signature(tool_name: str, args: dict[str, object]) -> str:
    """
    Build tool metadata for signature.

    Args:
        tool_name: Registered tool name.
        args: Tool argument dictionary.

    Returns:
        Generated or formatted string value.
    """
    import json

    return f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"


def get_tool_rule(tool_name: str) -> ToolIntentRule | None:
    """
    Return intent metadata for a registered tool.

    Args:
        tool_name: Registered tool name.

    Returns:
        Tool intent rule when the tool is registered; otherwise None.
    """
    from app.tools.registry import get_tool

    tool = get_tool(tool_name)
    if tool is None:
        return None
    return ToolIntentRule(
        announcement=tool.announcement or tool_announcement_for(tool_name),
        keywords=tool.keywords,
    )
