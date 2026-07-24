from app.assistant.agent_router import AgentRouter
from app.assistant.orchestrator import AgentOrchestrator
from app.assistant.rules.intents import (
    extract_self_improve_goal,
    is_self_improve_follow_up,
    is_self_improve_request,
)
from app.intents.self_improve import normalize_self_improve_goal


class _FakeClient:
    def complete(self, messages) -> str:
        return '{"aligned": true, "problems": []}'


def test_self_improve_intent() -> None:
    assert is_self_improve_request("Improve yourself by adding restart support.")
    assert is_self_improve_request("Improve yourself by making timer messages clearer.")
    assert is_self_improve_request("Draft an improvement plan for clearer timer messages.")


def test_router_draft_improvement_plan_command_routes_to_tool() -> None:
    decision = AgentRouter().decide(
        "Draft an improvement plan for clearer timer messages.",
        conversation_id="agent-default",
        history=[],
    )
    assert decision.mode == "tool"
    assert decision.tool_name == "draft_improvement_plan"
    assert decision.tool_args == {"goal": "clearer timer messages"}


def test_normalize_self_improve_goal_strips_draft_plan_phrasing() -> None:
    assert (
        normalize_self_improve_goal("Draft an improvement plan for clearer timer messages.")
        == "clearer timer messages"
    )
    assert (
        extract_self_improve_goal("Improve yourself by making timer messages clearer.")
        == "making timer messages clearer"
    )


def test_router_self_improve_routes_before_timer_cancel() -> None:
    decision = AgentRouter().decide(
        "Improve yourself by making timer messages clearer.",
        conversation_id="agent-default",
        history=[],
    )
    assert decision.mode == "tool"
    assert decision.tool_name == "draft_improvement_plan"


def test_wipe_confirmation_ignores_clear_inside_other_words() -> None:
    from app.assistant.rules.intents import needs_wipe_confirmation

    assert not needs_wipe_confirmation("Improve yourself by making timer messages clearer.")
    assert needs_wipe_confirmation("Clear your memory.")


def test_self_improve_follow_up_detects_plan_implementation_requests() -> None:
    assert is_self_improve_follow_up("go ahead")
    assert is_self_improve_follow_up("Implement the plan")
    assert not is_self_improve_follow_up("What time is it?")


def test_orchestrator_blocks_plan_implementation_when_plan_is_waiting(
    monkeypatch, tmp_path
) -> None:
    from app.memory import improvement_plans
    from app.memory.db import create_db_and_tables

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.sqlite3'}")
    create_db_and_tables()
    improvement_plans.create_plan(
        title="Clearer timer messages",
        goal="clearer timer messages",
        body="Summary\nImprove timer copy.",
        files=["app/runtime/status_copy.py"],
    )

    content, _speak = AgentOrchestrator().respond("Go ahead.", conversation_id="default")

    assert "only saves a text plan" in content.lower()
    assert "do not create branches" in content.lower()
