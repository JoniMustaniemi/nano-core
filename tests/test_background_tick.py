from datetime import UTC, datetime, timedelta

from app.assistant.pending import pending_interactions
from app.common.types import ProactiveOffer
from app.config import get_settings
from app.memory import improvement_plans, internal_notes
from app.memory.db import create_db_and_tables
from app.memory.internal_note_service import InternalNoteService
from app.proactive.background_tick import _run_background_plan_draft, run_proactive_background_tick
from app.proactive.store import proactive_store
from app.runtime.activity import activity
from app.runtime.user_activity import user_activity
from app.tools.improvement_plan_service import IMPROVEMENT_PLAN_COMPLETED_SILENT_SOURCE


class _DraftClient:
    def complete(self, messages, **kwargs) -> str:
        content = messages[-1]["content"]
        if "Known files:" in content:
            return '{"files_to_read": ["app/main.py"]}'
        if "File index" in content:
            return '{"files_to_read": ["app/main.py"]}'
        return (
            "Summary\n"
            "Clearer timer errors.\n"
            "Target file\n"
            "app/main.py\n"
            "Proposed change\n"
            "- Improve error copy.\n"
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


def test_background_tick_starts_background_draft_when_idle(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick.sqlite3'}")
    monkeypatch.setenv("IDLE_EXAMINE_ENABLED", "false")
    create_db_and_tables()
    get_settings.cache_clear()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("value = 1\n", encoding="utf-8")

    _record_due_note()
    notes = internal_notes.list_pending_self_improvement_notes(limit=1)
    assert notes and notes[0].id is not None
    note_id = notes[0].id

    activity.reset()
    proactive_store.reset()
    pending_interactions.reset()
    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=700)

    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr(
        "app.proactive.background_tick.get_code_llm_client",
        lambda: _DraftClient(),
    )

    monkeypatch.setattr(
        "app.proactive.background_tick.run_background",
        lambda fn, *, label: fn(),
    )

    run_proactive_background_tick()

    assert pending_interactions.get("agent-default") is None
    assert proactive_store.snapshot()["waiting_for_presence"] is False
    assert improvement_plans.has_unprocessed_plan() is True
    plan = improvement_plans.get_unprocessed_plan()
    assert plan is not None
    assert plan.goal == "clearer timer errors"
    note = internal_notes.get_internal_note(note_id)
    assert note is not None
    assert note.delivered_at is not None
    assert internal_notes.list_pending_self_improvement_notes(limit=1) == []
    get_settings.cache_clear()


def test_background_tick_skips_when_outreach_disabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick-disabled.sqlite3'}")
    monkeypatch.setenv("PROACTIVE_OUTREACH_ENABLED", "false")
    monkeypatch.setenv("IDLE_EXAMINE_ENABLED", "false")
    create_db_and_tables()
    get_settings.cache_clear()

    _record_due_note()
    activity.reset()
    proactive_store.reset()
    pending_interactions.reset()
    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=700)

    run_proactive_background_tick()

    assert pending_interactions.get("agent-default") is None
    assert improvement_plans.has_unprocessed_plan() is False
    get_settings.cache_clear()


def test_background_draft_uses_silent_completion_source(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick-silent.sqlite3'}")
    create_db_and_tables()
    get_settings.cache_clear()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("value = 1\n", encoding="utf-8")

    _record_due_note()
    note = internal_notes.list_pending_self_improvement_notes(limit=1)[0]
    assert note.id is not None

    activity.reset()
    monkeypatch.setattr(
        "app.tools.self_improve_planning.file_selection_lines",
        lambda goal, limit=40: ["- app/main.py: Main entrypoint."],
    )
    monkeypatch.setattr(
        "app.proactive.background_tick.get_code_llm_client",
        lambda: _DraftClient(),
    )

    _run_background_plan_draft(note.id)

    snapshot = activity.snapshot()
    events = snapshot.get("events", [])
    completed = [
        event for event in events if event.get("source") == IMPROVEMENT_PLAN_COMPLETED_SILENT_SOURCE
    ]
    assert completed
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

    run_proactive_background_tick()

    assert pending_interactions.get("agent-default") is None
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

    run_proactive_background_tick()

    assert pending_interactions.get("agent-default") is None
    assert improvement_plans.has_unprocessed_plan() is False
    get_settings.cache_clear()


def test_background_tick_skips_crawl_when_plan_pipeline_active(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'tick-crawl-skip.sqlite3'}")
    monkeypatch.setenv("IDLE_EXAMINE_ENABLED", "true")
    monkeypatch.setenv("PROACTIVE_OUTREACH_ENABLED", "false")
    create_db_and_tables()
    get_settings.cache_clear()
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('nano')\n", encoding="utf-8")

    _record_due_note()
    activity.reset()
    proactive_store.reset()
    pending_interactions.reset()
    user_activity._last_activity_at = datetime.now(UTC) - timedelta(seconds=700)

    crawl_calls: list[str] = []

    class _CrawlClient:
        def complete(self, messages) -> str:
            crawl_calls.append("scan")
            return (
                '{"summary": "Timer module handles reminders.", '
                '"suggestion": "Add clearer timer errors.", '
                '"confidence": "medium"}'
            )

    monkeypatch.setattr(
        "app.proactive.background_tick.get_code_llm_client",
        lambda: _CrawlClient(),
    )
    monkeypatch.setattr(
        "app.memory.codebase_index.pick_next_scan_target",
        lambda all_paths: "app/main.py",
    )
    monkeypatch.setattr(
        "app.proactive.codebase_crawl.read_text_file",
        lambda path: "print('nano')",
    )
    monkeypatch.setattr(
        "app.proactive.codebase_crawl.file_content_hash",
        lambda path: "hash-main",
    )

    run_proactive_background_tick()

    assert crawl_calls == []
    assert len(internal_notes.list_pending_self_improvement_notes(limit=10)) == 1
    get_settings.cache_clear()
