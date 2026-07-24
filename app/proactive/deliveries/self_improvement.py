from __future__ import annotations

from app.assistant.response_source import ResponseSource, answer_source
from app.llm.protocol import LLMClient
from app.memory import improvement_plans, internal_notes
from app.proactive.registry import ProactiveDeliveryRegistry
from app.proactive.store import proactive_store
from app.proactive.types import ProactiveOffer
from app.tools.improvement_plan_service import ImprovementPlanService


class SelfImprovementSuggestionHandler:
    def deliver(
        self,
        *,
        offer: ProactiveOffer,
        client: LLMClient,
        conversation_id: str,
    ) -> ResponseSource:
        if improvement_plans.has_unprocessed_plan():
            return answer_source(
                user_message="proactive self-improvement",
                facts="A plan is already waiting for review. Open the Plans tab to read it.",
                conversation_id=conversation_id,
            )

        note_id = proactive_store.get_internal_note_id()
        note = internal_notes.get_internal_note(note_id) if note_id is not None else None
        if note is None:
            return answer_source(
                user_message="proactive self-improvement",
                facts="I could not draft a plan right now.",
                conversation_id=conversation_id,
            )

        result = ImprovementPlanService().draft_from_note(note, client=client)
        if not result.ok:
            return answer_source(
                user_message="proactive self-improvement",
                facts="I could not draft a plan right now.",
                conversation_id=conversation_id,
            )

        title = (result.title or offer.title or "improvement plan").strip()
        return answer_source(
            user_message="proactive self-improvement",
            facts=f"I finished a new improvement plan: {title}. Open the Plans tab to read it.",
            conversation_id=conversation_id,
        )


def register_delivery_handlers(registry: ProactiveDeliveryRegistry) -> None:
    handler = SelfImprovementSuggestionHandler()
    registry.register("self_improvement_suggestion", handler)
    registry.register("deferred_offer", handler)
