from helpers.agent_fixtures import (
    agent_respond,
    patch_agent,
)

from app.assistant.agent_router import AgentRouter
from app.assistant.rules import message_matches_any_tool_intent
from app.runtime.status_copy import CONFUSED_RESPONSES


class NoCallClient:
    def complete(self, messages) -> str:
        raise AssertionError("The model should not be called for confused routing.")


def test_message_matches_any_tool_intent_for_weather() -> None:
    assert message_matches_any_tool_intent("What's the weather?") is True


def test_message_matches_any_tool_intent_for_arithmetic() -> None:
    assert message_matches_any_tool_intent("What is 2 + 2?") is True


def test_message_matches_any_tool_intent_for_calendar() -> None:
    assert message_matches_any_tool_intent("What's on my calendar today?") is True


def test_message_matches_any_tool_intent_for_unmatched_chat() -> None:
    assert message_matches_any_tool_intent("How are you?") is False
    assert message_matches_any_tool_intent("Tell me a joke") is False


def test_agent_router_returns_confused_for_unmatched_message() -> None:
    decision = AgentRouter().decide(
        "How are you?",
        conversation_id="default",
        history=[],
    )
    assert decision.mode == "confused"


def test_agent_router_returns_planner_when_tool_keywords_match() -> None:
    decision = AgentRouter().decide(
        "What's the weather?",
        conversation_id="default",
        history=[],
    )
    assert decision.mode == "planner"


def test_agent_returns_confused_response_without_llm(monkeypatch, tmp_path) -> None:
    client = NoCallClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = agent_respond("How are you?")

    assert content in CONFUSED_RESPONSES


def test_agent_returns_confused_response_for_joke_request(monkeypatch, tmp_path) -> None:
    client = NoCallClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = agent_respond("Tell me a joke")

    assert content in CONFUSED_RESPONSES
