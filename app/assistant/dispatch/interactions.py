from __future__ import annotations

from collections.abc import Callable

from app.assistant.agent_router import RouteDecision
from app.assistant.answer_executor import AnswerExecutor
from app.assistant.flows.reboot import RebootInteractionHandler
from app.assistant.flows.service_restart import ServiceRestartInteractionHandler
from app.assistant.flows.timer import TimerInteractionHandler
from app.assistant.flows.wipe import WipeInteractionHandler
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.response_source import ResponseSource
from app.config import get_settings
from app.llm.protocol import LLMClient
from app.memory import repository

InteractionStart = Callable[..., ResponseSource]


class InteractionDispatcher:
    def __init__(
        self,
        *,
        timer_handler: TimerInteractionHandler,
        wipe_handler: WipeInteractionHandler,
        reboot_handler: RebootInteractionHandler,
        service_restart_handler: ServiceRestartInteractionHandler,
        answer_executor: AnswerExecutor,
    ) -> None:
        self.timer_handler = timer_handler
        self.answer_executor = answer_executor
        self._start_handlers: dict[str, InteractionStart] = {
            "wipe": wipe_handler.start,
            "reboot": reboot_handler.start,
            "service_restart": service_restart_handler.start,
        }
        self._pending_handlers = (
            timer_handler,
            wipe_handler,
            service_restart_handler,
            reboot_handler,
        )

    def dispatch(
        self,
        *,
        decision: RouteDecision,
        client: LLMClient,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource:
        interaction = decision.interaction
        if interaction in self._start_handlers:
            return self._start_handlers[interaction](
                conversation_id=conversation_id,
                message=message,
            )

        if interaction == "timer":
            timer_source = self.timer_handler.handle_direct_request(
                message=message,
                conversation_id=conversation_id,
                user_message=user_message,
            )
            if timer_source is not None:
                return timer_source

        return self.answer_executor.draft(
            client=client,
            message=message,
            conversation_id=conversation_id,
            history=repository.list_chat_messages(
                conversation_id=conversation_id,
                limit=get_settings().chat_history_limit,
            ),
        )

    def handle_pending(
        self,
        *,
        pending: PendingInteraction | None,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        if pending is None:
            return None

        for handler in self._pending_handlers:
            response = handler.handle_pending(
                pending=pending,
                message=message,
                conversation_id=conversation_id,
                user_message=user_message,
            )
            if response is not None:
                return response

        pending_interactions.clear(conversation_id)
        return None
