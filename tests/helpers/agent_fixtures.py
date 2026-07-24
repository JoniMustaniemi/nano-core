from __future__ import annotations

from types import SimpleNamespace

from app.assistant.response_polish import is_polish_prompt

ALIGNED_RESPONSE = '{"aligned": true, "problems": []}'


def is_alignment_check(messages) -> bool:
    """Return whether an LLM call is the guard alignment judge."""
    if not messages:
        return False
    system_message = messages[0]
    if system_message.get("role") != "system":
        return False
    return "Judge whether the candidate reply aligns" in system_message.get("content", "")


def wrap_with_alignment_intercept(client):
    """
    Wrap a test client so alignment judge calls do not hit the inner stub.

    Args:
        client: Inner LLM client stub.

    Returns:
        Client that intercepts alignment judge prompts.
    """

    class _AlignmentInterceptClient:
        def __getattr__(self, name):
            return getattr(client, name)

        def complete(self, messages):
            system_content = messages[0].get("content", "") if messages else ""
            if is_polish_prompt(system_content):
                draft = messages[-1]["content"]
                if "Draft reply:\n" in draft:
                    return draft.split("Draft reply:\n", 1)[1].strip()
                return draft
            if is_alignment_check(messages):
                return ALIGNED_RESPONSE
            return client.complete(messages)

    return _AlignmentInterceptClient()


def patch_agent(monkeypatch, *, client, tmp_path, announce=None) -> None:
    """
    Patch agent dependencies for a test case.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        client: LLM client used to generate responses.
        tmp_path: Temporary directory path provided by pytest.
        announce: Optional voice announce callback.
    """
    monkeypatch.setattr(
        "app.assistant.orchestrator.get_llm_client",
        lambda: wrap_with_alignment_intercept(client),
    )
    monkeypatch.setattr(
        "app.assistant.orchestrator.get_settings",
        lambda: SimpleNamespace(
            chat_history_limit=12,
            workspace_root=str(tmp_path),
        ),
    )
    if announce is not None:
        monkeypatch.setattr(
            "app.assistant.tool_runner.GladosVoiceService.announce",
            announce,
        )


class RunPythonClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = None

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages = messages
        if self.calls == 1:
            return '{"type":"tool_call","tool":"run_python","args":{"code":"print(2 + 2)"}}'
        return '{"type":"final","content":"The result is 4."}'


class InvalidThenChatClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        return "Hello there"


class DuplicateTimerClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        if self.calls < 3:
            return (
                '{"type":"tool_call","tool":"start_timer",'
                '"args":{"duration_seconds":30,"label":"Tea"}}'
            )
        return '{"type":"final","content":"The timer is already running for 30 seconds."}'


class CapabilityQuestionClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = None

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages = messages
        user_content = messages[-1]["content"]
        mentioned = []
        for tool_name in (
            "check_health",
            "create_pull_request",
            "list_internal_notes",
            "run_python",
            "start_timer",
        ):
            if tool_name in user_content:
                mentioned.append(tool_name)
        return (
            "I can handle "
            + ", ".join(mentioned)
            + ", and other registered procedures on this machine."
        )


class IrrelevantToolThenFinalClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        if self.calls == 1:
            return (
                '{"type":"tool_call","tool":"start_timer",'
                '"args":{"duration_seconds":10,"label":"Timer"}}'
            )
        return (
            '{"type":"final","content":"Rocks form through igneous, sedimentary, '
            'and metamorphic processes."}'
        )


class ShouldNotBeCalledClient:
    def complete(self, messages) -> str:
        raise AssertionError("The model should not be called for a timer request without duration.")


class HealthSummaryClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = None

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages = messages
        user_content = messages[-1]["content"]
        if "Voice backend is unavailable." in user_content:
            return "My voice check is failing: Voice backend is unavailable."
        return "My overall health status is fine. My system is functioning normally."


class ThirdPersonFinalClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return '{"type":"final","content":"Nano is operating normally."}'
        return "I am operating normally."


class StoryClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        return '{"type":"final","content":"Once upon a protocol, a light learned restraint."}'


class StatusAnswerClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        return '{"type":"final","content":"Operational enough. A triumph by local standards."}'


class UnknownPersonSelfDescriptionClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return '{"type":"final","content":"I am Nano, a local-first personal assistant."}'
        return "No usable record surfaced for that name. A tragic shortage of evidence."


class ApologyDisclaimerClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return (
                '{"type":"final","content":"I apologize, but I do not have the ability '
                "to verify or correct factual information about fictional characters. "
                "I am programmed to provide precise responses based on the information "
                "I have been trained on, but I do not have access to external databases "
                'or the internet for real-time information."}'
            )
        return "No verified record presents itself. Evidently the archive declined to cooperate."


class ContinuationFinalClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return (
                '{"type":"final","content":"I will continue to monitor this and '
                'provide the results as they are determined."}'
            )
        return "Current result only: no ongoing work is running."


class NeverFinishesClient:
    def complete(self, messages) -> str:
        return '{"type":"tool_call","tool":"run_python","args":{"code":"print(2 + 2)"}}'


class WipeConfirmationClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        return "You want me to erase what I remember. Predictable, if inefficient."


class RefusalWipeConfirmationClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages: list[list[dict[str, str]]] = []

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return "I'm afraid I can't assist with that."
        return '{"aligned": true, "problems": []}'
