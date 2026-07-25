"""Regression tests for natural-language UI command phrase matching."""

from helpers.ui_command_match import match_ui_command


def test_controls_show_phrases() -> None:
    phrases = (
        "show me the controls",
        "can I see the controls",
        "open the controls panel",
        "bring up the controls",
        "let me see the controls",
        "hey nano show me the controls please",
    )
    for phrase in phrases:
        result = match_ui_command(phrase)
        assert result == {"type": "controls", "action": "show"}, phrase


def test_controls_hide_phrases() -> None:
    phrases = (
        "hide the controls",
        "hide controls panel",
        "can you hide the controls",
    )
    for phrase in phrases:
        result = match_ui_command(phrase)
        assert result == {"type": "controls", "action": "hide"}, phrase


def test_controls_toggle_phrases() -> None:
    phrases = (
        "toggle controls",
        "hide/show controls",
        "hide show controls",
    )
    for phrase in phrases:
        result = match_ui_command(phrase)
        assert result == {"type": "controls", "action": "toggle"}, phrase


def test_plans_section_phrases() -> None:
    phrases = (
        "show me your plans",
        "take me to plans",
        "go to the plans tab",
        "what plans do you have",
    )
    for phrase in phrases:
        result = match_ui_command(phrase)
        assert result == {"type": "section", "target": "plans"}, phrase


def test_brains_section_phrases() -> None:
    phrases = (
        "show me your thoughts",
        "what's on your mind",
        "let me see your brains",
    )
    for phrase in phrases:
        result = match_ui_command(phrase)
        assert result == {"type": "section", "target": "brains"}, phrase


def test_storage_section_phrases() -> None:
    phrases = (
        "show me what you saved",
        "show saved stuff",
        "what did you save",
    )
    for phrase in phrases:
        result = match_ui_command(phrase)
        assert result == {"type": "section", "target": "storage"}, phrase


def test_commands_section_phrases() -> None:
    phrases = (
        "show quick actions",
        "open command list",
        "what commands are available",
        "list commands",
    )
    for phrase in phrases:
        result = match_ui_command(phrase)
        assert result == {"type": "section", "target": "commands"}, phrase


def test_close_phrases() -> None:
    phrases = (
        "close",
        "dismiss",
        "exit panel",
        "close this",
        "close it",
        "okay nano you can close the menu",
        "you can close the menu",
        "thanks you can close this",
    )
    for phrase in phrases:
        result = match_ui_command(phrase)
        assert result == {"type": "close"}, phrase


def test_close_negated_phrases_do_not_match() -> None:
    phrases = (
        "don't close the menu",
        "do not close this",
    )
    for phrase in phrases:
        assert match_ui_command(phrase) is None, phrase


def test_non_ui_phrases_do_not_match() -> None:
    phrases = (
        "tell me about controls engineering",
        "what is version control",
        "run a system analysis",
    )
    for phrase in phrases:
        assert match_ui_command(phrase) is None, phrase
