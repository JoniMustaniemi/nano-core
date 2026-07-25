from helpers.agent_fixtures import HealthSummaryClient, patch_agent

from app.assistant.agent import AgentService
from app.assistant.response_polish import is_polish_prompt


class _PolishFailsClient:
    """LLM stub that fails only on the polish pass."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        system_content = messages[0].get("content", "") if messages else ""
        if is_polish_prompt(system_content):
            return "Local LLM is not available yet."
        return '{"aligned": true, "problems": []}'


def test_agent_system_analysis_skips_polish_when_llm_unavailable(monkeypatch, tmp_path) -> None:
    client = _PolishFailsClient()
    patch_agent(monkeypatch, client=client, tmp_path=tmp_path, announce=lambda text: None)

    content = AgentService().respond("Can you run a system analysis for me?")

    assert "Here's how I'm running on your machine." in content
    assert "Local LLM is not available yet" not in content


def test_agent_routes_system_analysis_request(monkeypatch, tmp_path) -> None:
    client = HealthSummaryClient()
    patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda text: None,
    )

    content = AgentService().respond("Can you run a system analysis for me?")

    assert "Here's how I'm running on your machine." in content
    assert client.calls == 0


def test_is_system_analysis_request_matches_common_phrases() -> None:
    from app.assistant.rules.intents import is_system_analysis_request

    assert is_system_analysis_request("Can you run a system analysis for me?")
    assert is_system_analysis_request("run a system analysis")
    assert is_system_analysis_request("analyze my system")
