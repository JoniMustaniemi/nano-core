
from app.assistant.agent_router import AgentRouter
from app.assistant.rules.intents import is_self_improve_request
from app.proactive.store import proactive_store


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
    assert decision.tool_name == "propose_self_changes"


def test_wipe_confirmation_ignores_clear_inside_other_words() -> None:
    from app.assistant.rules.intents import needs_wipe_confirmation

    assert not needs_wipe_confirmation(
        "Improve yourself by making timer messages clearer."
    )
    assert needs_wipe_confirmation("Clear your memory.")


def test_router_self_improve_follow_up() -> None:
    proactive_store.reset()
    proactive_store.set_last_goal("clearer timer errors")
    decision = AgentRouter().decide("do it", conversation_id="agent-default", history=[])
    assert decision.mode == "tool"
    assert decision.tool_name == "propose_self_changes"
    assert decision.tool_args == {"goal": "clearer timer errors"}
    proactive_store.reset()
