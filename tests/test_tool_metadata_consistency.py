from app.assistant.rules.tools import build_tool_rules, get_tool_rule
from app.runtime.status_copy import (
    _TOOL_ACTIVITY_COMPLETED_TITLES,
    _TOOL_ACTIVITY_TITLES,
)
from app.tools.registry import list_tools, list_ui_tool_commands
from app.web.tool_commands import EXTRA_UI_COMMANDS, list_tool_commands


def test_every_registered_tool_has_activity_copy() -> None:
    registered = {tool.name for tool in list_tools()}
    assert registered == set(_TOOL_ACTIVITY_TITLES.keys())
    assert registered == set(_TOOL_ACTIVITY_COMPLETED_TITLES.keys())
    for tool in list_tools():
        assert _TOOL_ACTIVITY_TITLES[tool.name].strip()
        assert _TOOL_ACTIVITY_COMPLETED_TITLES[tool.name].strip()
        assert tool.announcement and tool.announcement.strip()


def test_tool_rules_derive_from_registry() -> None:
    rules = build_tool_rules()
    registered = {tool.name for tool in list_tools()}

    assert registered == set(rules.keys())
    for tool in list_tools():
        rule = rules[tool.name]
        assert rule.announcement
        assert rule.announcement == (tool.announcement or rule.announcement)
        assert rule.keywords == tool.keywords


def test_ui_commands_include_registered_tools_with_metadata() -> None:
    ui_tools = {tool.name for tool in list_ui_tool_commands()}
    commands = list_tool_commands()
    command_ids = {item["id"] for item in commands}

    assert ui_tools.issubset(command_ids)
    for tool in list_ui_tool_commands():
        match = next(item for item in commands if item["id"] == tool.name)
        assert match["label"] == tool.ui_label
        assert match["message"] == tool.ui_message
        assert match["category"] == tool.ui_category


def test_extra_ui_commands_are_not_registered_tools() -> None:
    registered = {tool.name for tool in list_tools()}
    for command in EXTRA_UI_COMMANDS:
        assert command.id not in registered


def test_draft_improvement_plan_is_not_a_ui_command() -> None:
    ui_tools = {tool.name for tool in list_ui_tool_commands()}
    command_ids = {item["id"] for item in list_tool_commands()}

    assert "draft_improvement_plan" not in ui_tools
    assert "draft_improvement_plan" not in command_ids


def test_get_tool_rule_matches_registry_metadata() -> None:
    tool = next(tool for tool in list_tools() if tool.name == "check_health")
    rule = get_tool_rule("check_health")

    assert rule is not None
    assert rule.announcement == tool.announcement
    assert "health check" in rule.keywords
