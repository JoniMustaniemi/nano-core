
from app.assistant.agent_router import AgentRouter
from app.assistant.rules.intents import (
    is_self_improve_request,
    is_self_update_request,
)
from app.proactive.store import proactive_store


class _FakeClient:
    def complete(self, messages) -> str:
        return '{"aligned": true, "problems": []}'


def test_self_improve_intent() -> None:
    assert is_self_improve_request("Improve yourself by adding restart support.")
    assert is_self_update_request("Pull the latest changes and restart.")


def test_router_self_improve_follow_up() -> None:
    proactive_store.reset()
    proactive_store.set_last_goal("clearer timer errors")
    decision = AgentRouter().decide("do it", conversation_id="agent-default", history=[])
    assert decision.mode == "tool"
    assert decision.tool_name == "propose_self_changes"
    assert decision.tool_args == {"goal": "clearer timer errors"}
    proactive_store.reset()


def test_router_self_update_interaction() -> None:
    decision = AgentRouter().decide(
        "Pull the latest changes and restart.",
        conversation_id="agent-default",
        history=[],
    )
    assert decision.mode == "interaction"
    assert decision.interaction == "self_update"
