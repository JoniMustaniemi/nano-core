from __future__ import annotations

from typing import Any

from app.assistant.agent_router import AgentRouter, RouteDecision
from app.assistant.answer_executor import AnswerExecutor
from app.assistant.flows.chat import AgentChatFlow
from app.assistant.flows.planner import AgentPlanner
from app.assistant.flows.presence_gate import PresenceGateHandler, presence_gate
from app.assistant.flows.timer import TimerInteractionHandler
from app.assistant.flows.wipe import WipeInteractionHandler
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.response_composer import ResponseComposer
from app.assistant.response_pipeline import finalize_response
from app.assistant.response_source import ResponseSource
from app.assistant.tool_executor import ToolExecutor
from app.assistant.tool_runner import ToolRunner
from app.config import get_settings
from app.llm.factory import get_llm_client
from app.llm.protocol import LLMClient
from app.memory import repository
from app.runtime import activity
from app.runtime.status_copy import RECEIVED_TITLE, route_acknowledgment
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
        presence_handler: PresenceGateHandler | None = None,
        planner: AgentPlanner | None = None,
    ) -> None:
        """
        Initialize orchestrator dependencies.

        Args:
            tool_runner: Tool runner value.
            router: Agent router value.
            composer: Response composer value.
            answer_executor: Answer executor value.
            tool_executor: Tool executor value.
            chat_flow: Chat flow value.
            timer_handler: Timer handler value.
            wipe_handler: Wipe handler value.
            planner: Agent planner value.
        """
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
        self.presence_handler = presence_handler or presence_gate
        self.planner = planner or AgentPlanner(
            tool_runner=self.tool_runner,
            chat_flow=self.chat_flow,
            answer_executor=self.answer_executor,
        )

    def respond(self, message: str, conversation_id: str = "default") -> tuple[str, bool]:
        """
        Respond to a user message through the unified pipeline.

        Args:
            message: User message text.
            conversation_id: Conversation identifier.

        Returns:
            Composed assistant response and whether it should be spoken aloud.
        """
        settings = get_settings()
        user_activity.touch()
        repository.add_chat_message(conversation_id=conversation_id, role="user", content=message)
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

    def compose_and_persist(self, *, client: LLMClient, source: ResponseSource) -> tuple[str, bool]:
        """
        Compose a response source and persist it.

        Args:
            client: LLM client used for composition.
            source: Structured response input.

        Returns:
            Composed assistant response.
        """
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
            pending_source = self._handle_pending_interaction(
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
            return self._dispatch_interaction(
                decision=decision,
                client=client,
                message=message,
                conversation_id=conversation_id,
                user_message=message,
            )

        if decision.mode == "tool":
            return self.tool_executor.run(
                user_message=message,
                conversation_id=conversation_id,
                tool_name=decision.tool_name or "",
                args=decision.tool_args or {},
            )

        if decision.mode == "capabilities":
            return self.answer_executor.draft_capabilities(
                client=client,
                message=message,
                conversation_id=conversation_id,
            )

        if decision.mode == "identity":
            return self.answer_executor.draft_identity(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )

        if decision.mode == "answer":
            return self.answer_executor.draft(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )

        messages = self.chat_flow.build_agent_messages(history=history, message=message)
        return self.planner.run(
            client=client,
            conversation_id=conversation_id,
            message=message,
            history=history,
            messages=messages,
        )

    def _dispatch_interaction(
        self,
        *,
        decision: RouteDecision,
        client: LLMClient,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource:
        if decision.interaction == "wipe":
            return self.wipe_handler.start(
                conversation_id=conversation_id,
                message=message,
            )

        if decision.interaction == "timer":
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

    def _handle_pending_interaction(
        self,
        *,
        pending: PendingInteraction | None,
        message: str,
        conversation_id: str,
        user_message: str,
    ) -> ResponseSource | None:
        if pending is None:
            return None

        if pending.kind == "presence_check":
            response = self.presence_handler.handle_pending(
                message=message,
                conversation_id=conversation_id,
                client=get_llm_client(),
            )
            if response is not None:
                return response

        handlers = (
            self.timer_handler,
            self.wipe_handler,
        )
        for handler in handlers:
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

    def _finalize(self, *, client: LLMClient, source: ResponseSource) -> tuple[str, bool]:
        return finalize_response(
            client,
            source,
            composer=self.composer,
            standby_source="assistant.orchestrator",
        )
