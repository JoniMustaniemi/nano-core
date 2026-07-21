from __future__ import annotations

from types import SimpleNamespace


def patch_agent(monkeypatch, *, client, tmp_path, announce=None) -> None:
    """
    Patch agent dependencies for a test case.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        client: LLM client used to generate responses.
        tmp_path: Temporary directory path provided by pytest.
        announce: Optional voice announce callback.
    """
    monkeypatch.setattr("app.assistant.orchestrator.get_llm_client", lambda: client)
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

    def complete(self, messages) -> str:
        self.calls += 1
        return (
            "I can answer questions, use local tools when needed, and help with tasks "
            "on this machine."
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
