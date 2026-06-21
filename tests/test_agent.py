from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.assistant.agent import AgentService
from app.assistant.pending import pending_interactions
from app.memory import repository
from app.memory.repository import list_recent_chat_messages


def _patch_agent(monkeypatch, *, client, tmp_path, announce=None) -> None:
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
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        if self.calls == 1:
            return (
                '{"type":"tool_call","tool":"run_python","args":{"code":"print(2 + 2)"}}'
            )
        return '{"type":"final","content":"The result is 4."}'


class _InvalidThenChatClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        return "Hello there"


class _DuplicateTimerClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        if self.calls < 3:
            return (
                '{"type":"tool_call","tool":"start_timer","args":{"duration_seconds":30,"label":"Tea"}}'
            )
        return '{"type":"final","content":"The timer is already running for 30 seconds."}'


class _CapabilityQuestionClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        return (
            "I can answer questions, use local tools when needed, and help with tasks "
            "on this machine."
        )


class _IrrelevantToolThenFinalClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        if self.calls == 1:
            return (
                '{"type":"tool_call","tool":"start_timer","args":{"duration_seconds":10,"label":"Timer"}}'
            )
        return (
            '{"type":"final","content":"Rocks form through igneous, sedimentary, '
            'and metamorphic processes."}'
        )


class _ShouldNotBeCalledClient:
    def complete(self, messages) -> str:
        raise AssertionError("The model should not be called for a timer request without duration.")


class _HealthSummaryClient:
    def __init__(self) -> None:
        self.calls = 0
        self.messages = None

    def complete(self, messages) -> str:
        self.calls += 1
        self.messages = messages
        return (
            "Nano's self-diagnostics report: My overall health status is fine. "
            "The user's system is functioning normally."
        )


class _NeverFinishesClient:
    def complete(self, messages) -> str:
        return '{"type":"tool_call","tool":"run_python","args":{"code":"print(2 + 2)"}}'


class _WipeConfirmationClient:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages) -> str:
        self.calls += 1
        return "You want me to erase what I remember. Predictable, if inefficient."


def test_agent_runs_a_legitimate_tool_call(monkeypatch, tmp_path) -> None:
    client = _RunPythonClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("What is 2 + 2?")

    assert content == "The result is 4."
    assert client.calls >= 2


def test_agent_announces_tool_calls(monkeypatch, tmp_path) -> None:
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

    assert content == "My overall health status is fine. My system is functioning normally."
    assert client.calls == 1
    assert '"checks"' not in client.messages[1]["content"]
    assert "speak in first person as nano" in client.messages[0]["content"].lower()
    assert "do not refer to nano as the user" in client.messages[0]["content"].lower()
    assert "This is Nano reporting on my own health." in client.messages[1]["content"]
    assert "My overall status is error." in client.messages[1]["content"]
    assert "- My database check is ok." in client.messages[1]["content"]


def test_agent_falls_back_to_plain_chat_when_model_skips_json(monkeypatch, tmp_path) -> None:
    client = _InvalidThenChatClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("hey nano")

    assert content == "Hello there"
    assert client.calls == 3


def test_agent_handles_explicit_timer_requests_without_model(monkeypatch, tmp_path) -> None:
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
    client = _CapabilityQuestionClient()
    _patch_agent(monkeypatch, client=client, tmp_path=tmp_path)

    content = AgentService().respond("What can you do?")

    assert "I can answer questions" in content
    assert client.calls == 1
    assert repository.list_reminders() == []


def test_agent_rejects_irrelevant_tool_calls(monkeypatch, tmp_path) -> None:
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
    _patch_agent(monkeypatch, client=_ShouldNotBeCalledClient(), tmp_path=tmp_path)

    content = AgentService().respond("Start a timer.")

    assert content == "How long should the timer run?"
    assert repository.list_reminders() == []


def test_agent_starts_timer_after_duration_follow_up(monkeypatch, tmp_path) -> None:
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
    _patch_agent(monkeypatch, client=_WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("keep me for now")

    content = AgentService().respond("Wipe your database.")

    assert "erase what I remember" in content
    assert "reply yes to proceed" in content.lower()
    assert repository.list_notes()[0].content == "keep me for now"


def test_agent_requires_confirmation_for_local_data_removal(monkeypatch, tmp_path) -> None:
    _patch_agent(monkeypatch, client=_WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("keep me for now")

    content = AgentService().respond("Remove local data.")

    assert "reply yes to proceed" in content.lower()
    assert repository.list_notes()[0].content == "keep me for now"


def test_agent_wipes_database_after_confirmation(monkeypatch, tmp_path) -> None:
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
    _patch_agent(monkeypatch, client=_WipeConfirmationClient(), tmp_path=tmp_path)
    repository.add_note("do not delete me")

    AgentService().respond("Wipe your database.")
    content = AgentService().respond("no")

    assert content == "Database wipe cancelled."
    assert repository.list_notes()[0].content == "do not delete me"


def test_agent_announces_tool_errors(monkeypatch, tmp_path) -> None:
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
