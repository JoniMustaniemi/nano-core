
from app.assistant.agent_router import AgentRouter
from app.assistant.rules.intents import is_self_improve_request


class _FakeClient:
    def complete(self, messages) -> str:
        return '{"aligned": true, "problems": []}'


def test_self_improve_intent() -> None:
    assert is_self_improve_request("Improve yourself by adding restart support.")
    assert is_self_improve_request("Improve yourself by making timer messages clearer.")


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

    assert not needs_wipe_confirmation(
        "Improve yourself by making timer messages clearer."
    )
    assert needs_wipe_confirmation("Clear your memory.")
