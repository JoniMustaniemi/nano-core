from __future__ import annotations

from app.assistant.response_source import ResponseSource, answer_source
from app.llm.protocol import LLMClient
from app.proactive.types import ProactiveOffer


class SelfImprovementSuggestionHandler:
  def deliver(
    self,
    *,
    offer: ProactiveOffer,
    client: LLMClient,
    conversation_id: str,
  ) -> ResponseSource:
    _ = client
    goal = str(offer.payload.get("goal", "")).strip()
    follow_up = " Say 'do it' if you want me to prepare a pull request."
    summary = offer.summary.strip()
    if goal and goal not in summary:
      summary = f"{summary} ({goal})"
    return answer_source(
      user_message="proactive self-improvement",
      facts=f"{summary}{follow_up}",
      conversation_id=conversation_id,
    )


def register_delivery_handlers(registry) -> None:
  handler = SelfImprovementSuggestionHandler()
  registry.register("self_improvement_suggestion", handler)
  registry.register("deferred_offer", handler)
