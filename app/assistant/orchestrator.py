from __future__ import annotations

from typing import Any, Literal

from app.assistant.agent_router import AgentRouter, RouteDecision
from app.assistant.answer_executor import AnswerExecutor
from app.assistant.dispatch import InteractionDispatcher, RouteDispatcher
from app.assistant.flows.chat import AgentChatFlow
from app.assistant.flows.planner import AgentPlanner
from app.assistant.flows.reboot import RebootInteractionHandler
from app.assistant.flows.service_restart import ServiceRestartInteractionHandler
from app.assistant.flows.timer import TimerInteractionHandler
from app.assistant.flows.wipe import WipeInteractionHandler
from app.assistant.pending import pending_interactions
from app.assistant.response_composer import ResponseComposer
from app.assistant.response_pipeline import finalize_response
from app.assistant.response_source import ResponseSource
from app.assistant.rules import (
    is_capability_question,
    is_identity_question,
    is_silent_ui_command,
)
from app.assistant.tool_executor import ToolExecutor
from app.assistant.tool_runner import ToolRunner
from app.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.protocol import LLMClient
from app.memory import repository
from app.runtime import activity
from app.runtime.status_copy import (
    RECEIVED_DETAIL,
    RECEIVED_TITLE,
    THINKING_DETAIL,
    THINKING_TITLE,
    route_acknowledgment,
)
from app.runtime.user_activity import user_activity


class AgentOrchestrator:
    """
    Unified respond pipeline: route, execute, compose, persist.
    """

    def __init__(
        self,
        *,
        tool_runner: ToolRunner | None = None,
        router: AgentRouter | None = None,
        composer: ResponseComposer | None = None,
        answer_executor: AnswerExecutor | None = None,
        tool_executor: ToolExecutor | None = None,
        chat_flow: AgentChatFlow | None = None,
        timer_handler: TimerInteractionHandler | None = None,
        wipe_handler: WipeInteractionHandler | None = None,
        reboot_handler: RebootInteractionHandler | None = None,
        service_restart_handler: ServiceRestartInteractionHandler | None = None,
        planner: AgentPlanner | None = None,
    ) -> None:
        self.tool_runner = tool_runner or ToolRunner()
        self.router = router or AgentRouter()
        self.composer = composer or ResponseComposer()
        self.answer_executor = answer_executor or AnswerExecutor()
        self.tool_executor = tool_executor or ToolExecutor(tool_runner=self.tool_runner)
        self.chat_flow = chat_flow or AgentChatFlow()
        self.timer_handler = timer_handler or TimerInteractionHandler(
            tool_runner=self.tool_runner,
            tool_executor=self.tool_executor,
        )
        self.wipe_handler = wipe_handler or WipeInteractionHandler()
        self.reboot_handler = reboot_handler or RebootInteractionHandler()
        self.service_restart_handler = service_restart_handler or ServiceRestartInteractionHandler()
        self.planner = planner or AgentPlanner(
            tool_runner=self.tool_runner,
            chat_flow=self.chat_flow,
            answer_executor=self.answer_executor,
        )
        self.interaction_dispatcher = InteractionDispatcher(
            timer_handler=self.timer_handler,
            wipe_handler=self.wipe_handler,
            reboot_handler=self.reboot_handler,
            service_restart_handler=self.service_restart_handler,
            answer_executor=self.answer_executor,
        )
        self.route_dispatcher = RouteDispatcher(
            tool_executor=self.tool_executor,
            answer_executor=self.answer_executor,
            planner=self.planner,
        )

    def respond(
        self,
        message: str,
        conversation_id: str = "default",
        *,
        mode: Literal["chat", "agent"] = "agent",
    ) -> tuple[str, bool]:
        if mode == "chat":
            try:
                return self._respond_chat(message, conversation_id=conversation_id)
            except Exception:
                activity.release_to_idle(source="assistant.orchestrator")
                raise

        settings = get_settings()
        user_activity.touch()
        if not is_silent_ui_command(message):
            repository.add_chat_message(
                conversation_id=conversation_id, role="user", content=message
            )
        try:
            history = repository.list_chat_messages(
                conversation_id=conversation_id,
                limit=settings.chat_history_limit,
            )
            client = get_llm_client()
            source = self._resolve_source(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )
            return self._finalize(client=client, source=source)
        except Exception:
            activity.release_to_idle(source="assistant.orchestrator")
            raise

    def _respond_chat(self, message: str, *, conversation_id: str) -> tuple[str, bool]:
        settings = get_settings()
        user_activity.touch()
        activity.working(
            title=RECEIVED_TITLE,
            detail=RECEIVED_DETAIL,
            source="assistant.chat",
        )
        repository.add_chat_message(conversation_id=conversation_id, role="user", content=message)
        history = repository.list_chat_messages(
            conversation_id=conversation_id,
            limit=settings.chat_history_limit,
        )
        client = get_llm_client()
        activity.working(
            title=THINKING_TITLE,
            detail=THINKING_DETAIL,
            source="assistant.chat",
        )
        if is_capability_question(message):
            source = self.answer_executor.draft_capabilities(
                client=client,
                message=message,
                conversation_id=conversation_id,
            )
        elif is_identity_question(message):
            source = self.answer_executor.draft_identity(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )
        else:
            source = self.answer_executor.draft(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )
        return finalize_response(
            client,
            source,
            composer=self.composer,
            standby_source="assistant.chat",
        )

    def compose_and_persist(self, *, client: LLMClient, source: ResponseSource) -> tuple[str, bool]:
        return self._finalize(client=client, source=source)

    def _resolve_source(
        self,
        *,
        client: LLMClient,
        message: str,
        conversation_id: str,
        history: list[Any],
    ) -> ResponseSource:
        decision = self.router.decide(
            message,
            conversation_id=conversation_id,
            history=history,
        )
        ack_title, ack_detail = route_acknowledgment(
            mode=decision.mode,
            tool_name=decision.tool_name,
            interaction=decision.interaction,
        )
        activity.working(
            title=ack_title,
            detail=ack_detail,
            source="assistant.orchestrator.route",
        )
        if decision.mode not in {"planner", "tool"} and ack_title != RECEIVED_TITLE:
            self.tool_runner.announce_message(ack_title)
        return self._dispatch(
            decision=decision,
            client=client,
            message=message,
            conversation_id=conversation_id,
            history=history,
        )

    def _dispatch(
        self,
        *,
        decision: RouteDecision,
        client: LLMClient,
        message: str,
        conversation_id: str,
        history: list[Any],
    ) -> ResponseSource:
        if decision.mode == "pending":
            pending_source = self.interaction_dispatcher.handle_pending(
                pending=pending_interactions.get(conversation_id),
                message=message,
                conversation_id=conversation_id,
                user_message=message,
            )
            if pending_source is not None:
                return pending_source
            pending_interactions.clear(conversation_id)
            decision = self.router.decide(
                message,
                conversation_id=conversation_id,
                history=history,
            )

        if decision.mode == "interaction":
            return self.interaction_dispatcher.dispatch(
                decision=decision,
                client=client,
                message=message,
                conversation_id=conversation_id,
                user_message=message,
            )

        messages = (
            self.chat_flow.build_agent_messages(history=history, message=message)
            if decision.mode == "planner"
            else None
        )
        return self.route_dispatcher.dispatch(
            decision=decision,
            client=client,
            message=message,
            conversation_id=conversation_id,
            history=history,
            messages=messages,
        )

    def _finalize(self, *, client: LLMClient, source: ResponseSource) -> tuple[str, bool]:
        return finalize_response(
            client,
            source,
            composer=self.composer,
            standby_source="assistant.orchestrator",
        )
