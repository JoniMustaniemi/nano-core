import json
from datetime import UTC, datetime, timedelta

from app.assistant.agent_router import AgentRouter
from app.assistant.rules.intents import is_vague_self_improve_goal
from app.memory.db import create_db_and_tables
from app.memory.internal_note_service import InternalNoteService
from app.proactive.types import ProactiveOffer
from app.tools import get_tool
from app.tools.improvement_plan_service import ImprovementPlanResult


def _record_self_improve_note(
    *,
    goal: str,
    summary: str = "Make timer errors clearer.",
    files: list[str] | None = None,
    next_attempt_at: datetime | None = None,
) -> None:
    payload: dict[str, object] = {"goal": goal}
    if files is not None:
        payload["files"] = files
    offer = ProactiveOffer(
        kind="self_improvement_suggestion",
        title="Improve timers",
        summary=summary,
        payload=payload,
        created_at=datetime.now(UTC),
    )
    InternalNoteService().record_from_offer(
        offer,
        next_attempt_at=next_attempt_at or datetime.now(UTC) + timedelta(hours=1),
    )


def test_is_vague_self_improve_goal() -> None:
    assert is_vague_self_improve_goal("")
    assert is_vague_self_improve_goal("general improvement")
    assert is_vague_self_improve_goal("Improve yourself")
    assert not is_vague_self_improve_goal("making timer messages clearer")


def test_resolve_self_improve_goal_uses_pending_note(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'resolve.sqlite3'}")
    create_db_and_tables()
    _record_self_improve_note(goal="clearer timer errors")

    goal, note_id, preferred_files = InternalNoteService().resolve_self_improve_goal("improve yourself")

    assert goal == "clearer timer errors"
    assert note_id is not None
    assert preferred_files == []


def test_resolve_self_improve_goal_keeps_explicit_goal(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'explicit.sqlite3'}")
    create_db_and_tables()
    _record_self_improve_note(goal="clearer timer errors")

    goal, note_id, preferred_files = InternalNoteService().resolve_self_improve_goal("add restart support")

    assert goal == "add restart support"
    assert note_id is None
    assert preferred_files == []


def test_resolve_self_improve_goal_falls_back_without_notes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'fallback.sqlite3'}")
    create_db_and_tables()

    goal, note_id, preferred_files = InternalNoteService().resolve_self_improve_goal("")

    assert goal == "general improvement"
    assert note_id is None
    assert preferred_files == []


def test_draft_improvement_plan_marks_note_delivered_on_success(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'delivered.sqlite3'}")
    create_db_and_tables()
    _record_self_improve_note(goal="clearer timer errors")
    service = InternalNoteService()
    pending = service.top_pending_self_improvement_note()
    assert pending is not None
    note_id = pending.id
    assert note_id is not None

    tool = get_tool("draft_improvement_plan")
    assert tool is not None

    monkeypatch.setattr(
        "app.tools.self_improve_tools.ImprovementPlanService.draft",
        lambda self, client, goal, preferred_files=None, source_note_id=None: ImprovementPlanResult(
            ok=True,
            step="complete",
            plan_id=1,
            title=goal,
            goal=goal,
        ),
    )
    monkeypatch.setattr(
        "app.tools.self_improve_tools.get_llm_client",
        lambda: object(),
    )

    raw = tool.handler({"goal": "improve yourself"})
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["goal"] == "clearer timer errors"
    assert payload["internal_note_id"] == note_id

    refreshed = service.top_pending_self_improvement_note()
    assert refreshed is None
    delivered = service.top_priority_due_note()
    assert delivered is None


def test_router_bare_improve_yourself_routes_to_tool() -> None:
    decision = AgentRouter().decide(
        "Improve yourself",
        conversation_id="agent-default",
        history=[],
    )
    assert decision.mode == "tool"
    assert decision.tool_name == "draft_improvement_plan"
    assert decision.tool_args == {"goal": "Improve yourself"}


def test_resolve_self_improve_goal_returns_preferred_files_from_note(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'files.sqlite3'}")
    create_db_and_tables()
    _record_self_improve_note(
        goal="improve message helpers",
        files=["app/assistant/rules/messages.py"],
    )

    goal, note_id, preferred_files = InternalNoteService().resolve_self_improve_goal("improve yourself")

    assert goal == "improve message helpers"
    assert note_id is not None
    assert preferred_files == ["app/assistant/rules/messages.py"]
