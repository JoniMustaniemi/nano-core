from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.assistant.agent import AgentService
from app.assistant.pending import pending_interactions
from app.memory import repository
from app.memory.repository import list_recent_chat_messages


def _patch_agent(monkeypatch, *, client, tmp_path, announce=None) -> None:
    """
    Patch agent dependencies for a test case.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        client: LLM client used to generate responses.
        tmp_path: Temporary directory path provided by pytest.
        announce: Announce value.

    Returns:
        None.
    """
    monkeypatch.setattr("app.assistant.agent.get_llm_client", lambda: client)
    monkeypatch.setattr(
        "app.assistant.agent.get_settings",
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


class _RunPythonClient:
    def __init__(self) -> None:
        """
        Initialize the _RunPythonClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = None

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages = messages
        if self.calls == 1:
            return '{"type":"tool_call","tool":"run_python","args":{"code":"print(2 + 2)"}}'
        return '{"type":"final","content":"The result is 4."}'


class _InvalidThenChatClient:
    def __init__(self) -> None:
        """
        Initialize the _InvalidThenChatClient instance.

        Returns:
            None.
        """
        self.calls = 0

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        return "Hello there"


class _DuplicateTimerClient:
    def __init__(self) -> None:
        """
        Initialize the _DuplicateTimerClient instance.

        Returns:
            None.
        """
        self.calls = 0

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        if self.calls < 3:
            return (
                '{"type":"tool_call","tool":"start_timer",'
                '"args":{"duration_seconds":30,"label":"Tea"}}'
            )
        return '{"type":"final","content":"The timer is already running for 30 seconds."}'


class _CapabilityQuestionClient:
    def __init__(self) -> None:
        """
        Initialize the _CapabilityQuestionClient instance.

        Returns:
            None.
        """
        self.calls = 0

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        return (
            "I can answer questions, use local tools when needed, and help with tasks "
            "on this machine."
        )


class _IrrelevantToolThenFinalClient:
    def __init__(self) -> None:
        """
        Initialize the _IrrelevantToolThenFinalClient instance.

        Returns:
            None.
        """
        self.calls = 0

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
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


class _ShouldNotBeCalledClient:
    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.

        Raises:
            AssertionError: If the operation cannot be completed.
        """
        raise AssertionError("The model should not be called for a timer request without duration.")


class _HealthSummaryClient:
    def __init__(self) -> None:
        """
        Initialize the _HealthSummaryClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = None

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages = messages
        user_content = messages[-1]["content"]
        if "Voice backend is unavailable." in user_content:
            return "My voice check is failing: Voice backend is unavailable."
        return (
            "My overall health status is fine. "
            "My system is functioning normally."
        )


class _HealthIntroSummaryClient:
    def __init__(self) -> None:
        """
        Initialize the _HealthIntroSummaryClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return (
                "I am Nano, a local-first personal assistant with the personality "
                "of a clinical and sarcastic overseer. My overall status is fine. "
                "No issues were detected in my system."
            )
        return "All clear. No issues surfaced."


class _VagueFailingHealthSummaryClient:
    def __init__(self) -> None:
        """
        Initialize the _VagueFailingHealthSummaryClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return "My health status is error."
        return "My test_failure check is failing: Testing the warning path."


class _SpecificFailingHealthSummaryClient:
    def __init__(self) -> None:
        """
        Initialize the _SpecificFailingHealthSummaryClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        return "My test_failure check is failing: Testing the warning path."


class _ContinuationHealthSummaryClient:
    def __init__(self) -> None:
        """
        Initialize the _ContinuationHealthSummaryClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return (
                "I will continue to run the checks and provide you with the results "
                "as they are determined."
            )
        return "My test_failure check is failing: Testing the warning path."


class _ContinuationAllClearHealthSummaryClient:
    def __init__(self) -> None:
        """
        Initialize the _ContinuationAllClearHealthSummaryClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return "I will continue to run the checks and provide results as they are determined."
        return "All clear. No ongoing diagnostic work remains."


class _ThirdPersonFinalClient:
    def __init__(self) -> None:
        """
        Initialize the _ThirdPersonFinalClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return '{"type":"final","content":"Nano is operating normally."}'
        return "I am operating normally."


class _ThirdPersonHealthSummaryClient:
    def __init__(self) -> None:
        """
        Initialize the _ThirdPersonHealthSummaryClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return "Nano is healthy."
        return "I am healthy."


class _StoryClient:
    def __init__(self) -> None:
        """
        Initialize the _StoryClient instance.

        Returns:
            None.
        """
        self.calls = 0

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        return '{"type":"final","content":"Once upon a protocol, a light learned restraint."}'


class _StatusAnswerClient:
    def __init__(self) -> None:
        """
        Initialize the _StatusAnswerClient instance.

        Returns:
            None.
        """
        self.calls = 0

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        return '{"type":"final","content":"Operational enough. A triumph by local standards."}'


class _UnknownPersonSelfDescriptionClient:
    def __init__(self) -> None:
        """
        Initialize the _UnknownPersonSelfDescriptionClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return (
                '{"type":"final","content":"I am Nano, a local-first personal assistant."}'
            )
        return "No usable record surfaced for that name. A tragic shortage of evidence."


class _ApologyDisclaimerClient:
    def __init__(self) -> None:
        """
        Initialize the _ApologyDisclaimerClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
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


class _ContinuationFinalClient:
    def __init__(self) -> None:
        """
        Initialize the _ContinuationFinalClient instance.

        Returns:
            None.
        """
        self.calls = 0
        self.messages = []

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        self.messages.append(messages)
        if self.calls == 1:
            return (
                '{"type":"final","content":"I will continue to monitor this and '
                'provide the results as they are determined."}'
            )
        return "Current result only: no ongoing work is running."


class _NeverFinishesClient:
    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        return '{"type":"tool_call","tool":"run_python","args":{"code":"print(2 + 2)"}}'


class _WipeConfirmationClient:
    def __init__(self) -> None:
        """
        Initialize the _WipeConfirmationClient instance.

        Returns:
            None.
        """
        self.calls = 0

    def complete(self, messages) -> str:
        """
        Provide test support for complete.

        Args:
            messages: Conversation messages to send to the model.

        Returns:
            Generated or formatted string value.
        """
        self.calls += 1
        return "You want me to erase what I remember. Predictable, if inefficient."


def test_agent_runs_a_legitimate_tool_call(monkeypatch, tmp_path) -> None:
    """
    Verify that agent runs a legitimate tool call.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _RunPythonClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("What is 2 + 2?")

    assert content == "The result is 4."
    assert client.calls >= 2
    assert "never refer to nano in third person" in client.messages[0]["content"].lower()


def test_agent_announces_tool_calls(monkeypatch, tmp_path) -> None:
    """
    Verify that agent announces tool calls.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _RunPythonClient()
    announcements: list[str] = []
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: announcements.append(text),
    )

    AgentService().respond("What is 2 + 2?")

    assert announcements == ["Running a local procedure."]


def test_agent_can_check_its_own_health(monkeypatch, tmp_path) -> None:
    """
    Verify that agent can check its own health.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _HealthSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
            SimpleNamespace(name="voice", ok=False, detail="Voice backend is unavailable."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My voice check is failing: Voice backend is unavailable."
    assert client.calls == 1
    assert '"checks"' not in client.messages[1]["content"]
    assert "you are speaking as nano" in client.messages[0]["content"].lower()
    assert "never refer to nano in third person" in client.messages[0]["content"].lower()
    assert "This is Nano reporting on my own health." in client.messages[1]["content"]
    assert "My overall status is error." in client.messages[1]["content"]
    assert "- My voice check is error. Voice backend is unavailable." in client.messages[1]["content"]
    assert "Database is reachable." not in client.messages[1]["content"]


def test_agent_health_summary_removes_identity_intro(monkeypatch, tmp_path) -> None:
    """
    Verify that health summaries do not include identity or personality introductions.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _HealthIntroSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "All clear. No issues surfaced."
    assert client.calls == 2
    assert "Do not introduce yourself" in client.messages[0][0]["content"]
    assert "I am Nano" in client.messages[1][1]["content"]


def test_agent_health_summary_names_failing_check(monkeypatch, tmp_path) -> None:
    """
    Verify that failing health summaries name the failing check and detail.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _VagueFailingHealthSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
            SimpleNamespace(name="test_failure", ok=False, detail="Testing the warning path."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My test_failure check is failing: Testing the warning path."
    assert client.calls == 2
    assert "previous answer was too vague" in client.messages[1][0]["content"].lower()
    assert "test_failure: Testing the warning path." in client.messages[1][1]["content"]


def test_agent_health_summary_keeps_specific_failure_answer(monkeypatch, tmp_path) -> None:
    """
    Verify that specific failing health summaries are not rewritten.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _SpecificFailingHealthSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="test_failure", ok=False, detail="Testing the warning path."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My test_failure check is failing: Testing the warning path."
    assert client.calls == 1


def test_agent_health_summary_rewrites_unsupported_continuation(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that health summaries do not promise later results.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ContinuationHealthSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="test_failure", ok=False, detail="Testing the warning path."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "My test_failure check is failing: Testing the warning path."
    assert client.calls == 2
    assert "previous answer was too vague" in client.messages[1][0]["content"].lower()


def test_agent_all_clear_health_summary_rewrites_unsupported_continuation(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that all-clear health summaries do not promise later results.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ContinuationAllClearHealthSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "All clear. No ongoing diagnostic work remains."
    assert client.calls == 2
    assert "must not promise future/background work" in client.messages[1][0]["content"]


def test_agent_rewrites_third_person_final_answer(monkeypatch, tmp_path) -> None:
    """
    Verify that agent rewrites third-person self-reference in final answers.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ThirdPersonFinalClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("How are you?")

    assert content == "I am operating normally."
    assert client.calls == 2
    assert "rewrite it so you speak as nano in first person" in (
        client.messages[1][0]["content"].lower()
    )


def test_agent_rewrites_third_person_health_summary(monkeypatch, tmp_path) -> None:
    """
    Verify that health summaries are revised when they mention Nano in third person.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ThirdPersonHealthSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
        ],
    )

    content = AgentService().respond("Check your health.")

    assert content == "I am healthy."
    assert client.calls == 2
    assert "Nano is healthy." in client.messages[1][1]["content"]


def test_agent_does_not_run_health_check_for_story_about_status(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that story requests do not trigger diagnostics because they mention status.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _StoryClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: (_ for _ in ()).throw(AssertionError("health check should not run")),
    )

    content = AgentService().respond("Tell me a story about a status light.")

    assert content == "Once upon a protocol, a light learned restraint."
    assert client.calls == 1


def test_agent_rewrites_self_description_for_unknown_fact_question(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that unknown factual questions do not fall back to self-description.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _UnknownPersonSelfDescriptionClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("Who is Jake Blamey?")

    assert content == "No usable record surfaced for that name. A tragic shortage of evidence."
    assert client.calls == 2
    assert "personality-driven" in client.messages[1][0]["content"]
    assert "I am Nano" in client.messages[1][1]["content"]


def test_agent_rewrites_apology_disclaimer_for_missing_information(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that missing information answers do not apologize or use generic disclaimers.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ApologyDisclaimerClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("Who is Jake Blamey?")

    assert content == "No verified record presents itself. Evidently the archive declined to cooperate."
    assert client.calls == 2
    assert "Do not apologize" in client.messages[1][0]["content"]
    assert "I apologize" in client.messages[1][1]["content"]


def test_agent_rewrites_unsupported_continuation_promise(monkeypatch, tmp_path) -> None:
    """
    Verify that final answers do not promise unsupported continued work.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ContinuationFinalClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("Check the situation.")

    assert content == "Current result only: no ongoing work is running."
    assert client.calls == 2
    assert "Do not tell the user to wait for more results" in client.messages[1][0]["content"]


def test_agent_does_not_run_health_check_for_status_question(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that status questions do not trigger diagnostics without explicit words.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _StatusAnswerClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: (_ for _ in ()).throw(AssertionError("health check should not run")),
    )

    content = AgentService().respond("What is your status?")

    assert content == "Operational enough. A triumph by local standards."
    assert client.calls == 1


def test_agent_runs_health_check_for_explicit_diagnostics_request(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that explicit diagnostics wording runs health diagnostics.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _HealthSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
        ],
    )

    content = AgentService().respond("Run diagnostics.")

    assert content == "My overall health status is fine. My system is functioning normally."
    assert client.calls == 1


def test_agent_health_summary_omits_passing_checks_when_everything_is_ok(
    monkeypatch,
    tmp_path,
) -> None:
    """
    Verify that agent health summary omits passing checks when everything is ok.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _HealthSummaryClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    monkeypatch.setattr(
        "app.tools.health_tools.run_health_checks",
        lambda: [
            SimpleNamespace(name="database", ok=True, detail="Database is reachable."),
            SimpleNamespace(name="voice", ok=True, detail="Voice backend is ready."),
        ],
    )

    AgentService().respond("Check your health.")

    assert "My overall status is ok." in client.messages[1]["content"]
    assert "No problems were found." in client.messages[1]["content"]
    assert "Database is reachable." not in client.messages[1]["content"]
    assert "Voice backend is ready." not in client.messages[1]["content"]


def test_agent_falls_back_to_plain_chat_when_model_skips_json(monkeypatch, tmp_path) -> None:
    """
    Verify that agent falls back to plain chat when model skips json.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _InvalidThenChatClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("hey nano")

    assert content == "Hello there"
    assert client.calls == 3


def test_agent_handles_explicit_timer_requests_without_model(monkeypatch, tmp_path) -> None:
    """
    Verify that agent handles explicit timer requests without model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _DuplicateTimerClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )

    content = AgentService().respond("Start a timer for 30 seconds.")
    reminders = repository.list_reminders()

    assert content == "The timer is set for 30 seconds."
    assert client.calls == 0
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Timer"


def test_agent_lists_active_timers_without_model(monkeypatch, tmp_path) -> None:
    """
    Verify that agent lists active timers without model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ShouldNotBeCalledClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    repository.add_reminder("[timer] Tea", datetime.now(UTC) + timedelta(minutes=5))

    content = AgentService().respond("Check active timers.")

    assert "Tea has" in content
    assert "remaining" in content


def test_agent_cancels_active_timers_without_model(monkeypatch, tmp_path) -> None:
    """
    Verify that agent cancels active timers without model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ShouldNotBeCalledClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    repository.add_reminder("[timer] Tea", datetime.now(UTC) + timedelta(minutes=5))

    content = AgentService().respond("Cancel timers.")

    assert content == "Cancelled 1 timer."
    assert repository.list_reminders() == []


def test_agent_cancel_timer_never_starts_timer(monkeypatch, tmp_path) -> None:
    """
    Verify that agent cancel timer never starts timer.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ShouldNotBeCalledClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )

    content = AgentService().respond("Cancel timer for two minutes.")

    assert content == "No active timers to cancel."
    assert repository.list_reminders() == []


def test_agent_checks_timers_instead_of_completing_pending_timer(monkeypatch, tmp_path) -> None:
    """
    Verify that agent checks timers instead of completing pending timer.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ShouldNotBeCalledClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )
    repository.add_reminder("[timer] Tea", datetime.now(UTC) + timedelta(minutes=5))

    first = AgentService().respond("Start a timer.")
    second = AgentService().respond("Check active timers.")
    reminders = repository.list_reminders()

    assert first == "How long should the timer run?"
    assert "Tea has" in second
    assert "remaining" in second
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Tea"


def test_agent_cancels_pending_timer_duration_request(monkeypatch, tmp_path) -> None:
    """
    Verify that agent cancels pending timer duration request.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _ShouldNotBeCalledClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )

    first = AgentService().respond("Start a timer.")
    second = AgentService().respond("Cancel timers.")

    assert first == "How long should the timer run?"
    assert second == "No active timers to cancel."
    assert pending_interactions.get("default") is None
    assert repository.list_reminders() == []


def test_agent_answers_capability_questions_without_tool_use(monkeypatch, tmp_path) -> None:
    """
    Verify that agent answers capability questions without tool use.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _CapabilityQuestionClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("What can you do?")

    assert "I can answer questions" in content
    assert client.calls == 1
    assert repository.list_reminders() == []


def test_agent_rejects_irrelevant_tool_calls(monkeypatch, tmp_path) -> None:
    """
    Verify that agent rejects irrelevant tool calls.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _IrrelevantToolThenFinalClient()
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )

    content = AgentService().respond("Tell me about rocks.")

    assert "igneous" in content
    assert repository.list_reminders() == []


def test_agent_asks_for_timer_duration_before_using_model(monkeypatch, tmp_path) -> None:
    """
    Verify that agent asks for timer duration before using model.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    _patch_agent(monkeypatch, client=_ShouldNotBeCalledClient(), tmp_path=tmp_path)

    content = AgentService().respond("Start a timer.")

    assert content == "How long should the timer run?"
    assert repository.list_reminders() == []


def test_agent_starts_timer_after_duration_follow_up(monkeypatch, tmp_path) -> None:
    """
    Verify that agent starts timer after duration follow up.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    _patch_agent(
        monkeypatch,
        client=_ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )

    first = AgentService().respond("Start a timer.")
    second = AgentService().respond("30 seconds")
    reminders = repository.list_reminders()

    assert first == "How long should the timer run?"
    assert second == "The timer is set for 30 seconds."
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Timer"


def test_agent_starts_timer_after_spoken_duration_follow_up(monkeypatch, tmp_path) -> None:
    """
    Verify that agent starts timer after spoken duration follow up.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    _patch_agent(
        monkeypatch,
        client=_ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )

    first = AgentService().respond("Start a timer.")
    second = AgentService().respond("five minutes")
    reminders = repository.list_reminders()

    assert first == "How long should the timer run?"
    assert second == "The timer is set for 5 minutes."
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Timer"


def test_agent_understands_spoken_timer_duration_in_single_request(monkeypatch, tmp_path) -> None:
    """
    Verify that agent understands spoken timer duration in single request.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    _patch_agent(
        monkeypatch,
        client=_ShouldNotBeCalledClient(),
        tmp_path=tmp_path,
        announce=lambda self, text: None,
    )

    content = AgentService().respond("Start a timer for five minutes.")
    reminders = repository.list_reminders()

    assert content == "The timer is set for 5 minutes."
    assert len(reminders) == 1
    assert reminders[0].content == "[timer] Timer"


def test_agent_requires_confirmation_before_wiping_database(monkeypatch, tmp_path) -> None:
    """
    Verify that agent requires confirmation before wiping database.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    _patch_agent(monkeypatch, client=_WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("keep me for now")

    content = AgentService().respond("Wipe your database.")

    assert "erase what I remember" in content
    assert "reply yes to proceed" in content.lower()
    assert repository.list_notes()[0].content == "keep me for now"


def test_agent_requires_confirmation_for_local_data_removal(monkeypatch, tmp_path) -> None:
    """
    Verify that agent requires confirmation for local data removal.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    _patch_agent(monkeypatch, client=_WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("keep me for now")

    content = AgentService().respond("Remove local data.")

    assert "reply yes to proceed" in content.lower()
    assert repository.list_notes()[0].content == "keep me for now"


def test_agent_wipes_database_after_confirmation(monkeypatch, tmp_path) -> None:
    """
    Verify that agent wipes database after confirmation.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    _patch_agent(monkeypatch, client=_WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("delete me")
    repository.add_reminder("stretch", datetime.now(UTC) + timedelta(minutes=5))

    first = AgentService().respond("Wipe your database.")
    second = AgentService().respond("yes")

    assert "reply yes to proceed" in first.lower()
    assert second == "Database wiped."
    assert repository.list_notes() == []
    assert repository.list_reminders(include_sent=True) == []
    assert list_recent_chat_messages() == []


def test_agent_cancels_database_wipe_on_no(monkeypatch, tmp_path) -> None:
    """
    Verify that agent cancels database wipe on no.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    _patch_agent(monkeypatch, client=_WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("do not delete me")

    AgentService().respond("Wipe your database.")
    content = AgentService().respond("no")

    assert content == "Database wipe cancelled."
    assert repository.list_notes()[0].content == "do not delete me"


def test_agent_announces_tool_errors(monkeypatch, tmp_path) -> None:
    """
    Verify that agent announces tool errors.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    client = _RunPythonClient()
    announcements: list[str] = []
    _patch_agent(
        monkeypatch,
        client=client,
        tmp_path=tmp_path,
        announce=lambda self, text: announcements.append(text),
    )
    monkeypatch.setattr(
        "app.assistant.tool_runner.get_tool",
        lambda name: SimpleNamespace(
            name=name,
            handler=lambda args: (_ for _ in ()).throw(RuntimeError("boom")),
        ),
    )

    content = AgentService().respond("What is 2 + 2?")

    assert content == "The result is 4."
    assert "I hit an error while trying to complete the task." in announcements


def test_agent_announces_step_limit_errors(monkeypatch, tmp_path) -> None:
    """
    Verify that agent announces step limit errors.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        tmp_path: Temporary directory path provided by pytest.

    Returns:
        None.
    """
    announcements: list[str] = []
    _patch_agent(
        monkeypatch,
        client=_NeverFinishesClient(),
        tmp_path=tmp_path,
        announce=lambda self, text: announcements.append(text),
    )

    content = AgentService().respond("What is 2 + 2?")

    assert content == "I tried to complete the task, but I hit the step limit."
    assert announcements[-1] == "I could not finish the task."
