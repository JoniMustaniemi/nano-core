from datetime import UTC, datetime, timedelta

from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.memory import improvement_plans
from app.memory.db import create_db_and_tables
from app.memory.internal_note_service import InternalNoteService
from app.proactive.background_tick import run_proactive_background_tick
from app.proactive.store import proactive_store
from app.proactive.types import ProactiveOffer
from app.runtime.activity import activity
from app.runtime.user_activity import user_activity


class _DraftClient:
    def complete(self, messages, **kwargs) -> str:
        content = messages[-1]["content"]
        if "Known files:" in content:
            return '{"files_to_read": ["app/main.py"]}'
        if "File index" in content:
            return '{"files_to_read": ["app/main.py"]}'
        return (
            '{"suggestion": "Improve startup logging.", '
            '"goal": "clearer startup logs", "confidence": "medium"}'
        )


def _record_due_note() -> None:
    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary="Make timer errors clearer.",
        payload={"goal": "clearer timer errors", "files": ["app/main.py"]},
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(offer, next_attempt_at=datetime.now(UTC))


def test_background_tick_auto_drafts_plan_when_idle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("value = 1\n", encoding="utf-8")

    _record_due_note()
    activity.reset()
    proactive_store.reset()
    pending_interactions.reset()
    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=700)

    monkeypatch.setattr(
        "app.proactive.background_tick.get_llm_client",
        lambda: _DraftClient(),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )

    run_proactive_background_tick()

    assert improvement_plans.has_unprocessed_plan() is True
    plan = improvement_plans.get_unprocessed_plan()
    assert plan is not None
    assert plan.goal == "clearer timer errors"
    get_settings.cache_clear()


def test_background_tick_skips_when_unprocessed_plan_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick2.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.proactive.background_tick.user_activity.is_idle",
        lambda _seconds: False,
    )

    improvement_plans.create_plan(
        title="Existing plan",
        goal="existing",
        body="Summary",
        files=["app/main.py"],
    )
    _record_due_note()
    activity.reset()
    proactive_store.reset()
    pending_interactions.reset()
    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=700)

    drafted = {"called": False}

    class _ShouldNotRun:
        def complete(self, messages, **kwargs) -> str:
            drafted["called"] = True
            return "should not run"

    monkeypatch.setattr(
        "app.proactive.background_tick.get_llm_client",
        lambda: _ShouldNotRun(),
    )

    run_proactive_background_tick()

    assert drafted["called"] is False
    assert len(improvement_plans.list_plans()) == 1
    get_settings.cache_clear()


def test_background_tick_skips_under_ten_minutes_idle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick3.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()

    _record_due_note()
    activity.reset()
    proactive_store.reset()
    pending_interactions.reset()
    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=200)

    drafted = {"called": False}

    class _ShouldNotRun:
        def complete(self, messages, **kwargs) -> str:
            drafted["called"] = True
            return "should not run"

    monkeypatch.setattr(
        "app.proactive.background_tick.get_llm_client",
        lambda: _ShouldNotRun(),
    )

    run_proactive_background_tick()

    assert drafted["called"] is False
    assert improvement_plans.has_unprocessed_plan() is False
    get_settings.cache_clear()


def test_background_tick_returns_to_standby_when_draft_fails(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick-fail.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("value = 1\n", encoding="utf-8")

    _record_due_note()
    activity.reset()
    proactive_store.reset()
    pending_interactions.reset()
    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=700)

    class _FailingClient:
        def complete(self, messages, **kwargs) -> str:
            content = messages[-1]["content"]
            if "Known files:" in content:
                return '{"files_to_read": ["app/main.py"]}'
            return ""

    monkeypatch.setattr(
        "app.proactive.background_tick.get_llm_client",
        lambda: _FailingClient(),
    )
    monkeypatch.setattr(
        "app.proactive.background_tick.user_activity.is_idle",
        lambda _seconds: False,
    )
    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )

    run_proactive_background_tick()

    assert activity.snapshot()["state"] == "standby"
    assert improvement_plans.has_unprocessed_plan() is False
    get_settings.cache_clear()
