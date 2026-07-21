from __future__ import annotations

from typing import Any

from app.assistant.agent_router import AgentRouter
from app.assistant.answer_executor import AnswerExecutor
from app.assistant.flows.chat import AgentChatFlow
from app.assistant.flows.github import PullRequestHandler
from app.assistant.flows.note import NoteInteractionHandler
from app.assistant.flows.planner import AgentPlanner
from app.assistant.flows.timer import TimerInteractionHandler
from app.assistant.flows.wipe import WipeInteractionHandler
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.response_composer import ResponseComposer
from app.assistant.response_source import ResponseSource
from app.assistant.router import get_llm_client
from app.assistant.tool_executor import ToolExecutor
from app.assistant.tool_runner import ToolRunner
from app.config import get_settings
from app.memory import repository
from app.runtime.activity import activity


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
        note_handler: NoteInteractionHandler | None = None,
        timer_handler: TimerInteractionHandler | None = None,
        wipe_handler: WipeInteractionHandler | None = None,
        pull_request_handler: PullRequestHandler | None = None,
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
            note_handler: Note handler value.
            timer_handler: Timer handler value.
            wipe_handler: Wipe handler value.
            pull_request_handler: Pull request handler value.
            planner: Agent planner value.
        """
        self.tool_runner = tool_runner or ToolRunner()
        self.router = router or AgentRouter()
        self.composer = composer or ResponseComposer()
        self.answer_executor = answer_executor or AnswerExecutor()
        self.tool_executor = tool_executor or ToolExecutor(tool_runner=self.tool_runner)
        self.chat_flow = chat_flow or AgentChatFlow()
        self.note_handler = note_handler or NoteInteractionHandler()
        self.timer_handler = timer_handler or TimerInteractionHandler(
            tool_runner=self.tool_runner,
            tool_executor=self.tool_executor,
        )
        self.wipe_handler = wipe_handler or WipeInteractionHandler()
        self.pull_request_handler = pull_request_handler or PullRequestHandler(
            tool_executor=self.tool_executor,
        )
        self.planner = planner or AgentPlanner(
            tool_runner=self.tool_runner,
            chat_flow=self.chat_flow,
            answer_executor=self.answer_executor,
        )

    def respond(self, message: str, conversation_id: str = "default") -> str:
        """
        Respond to a user message through the unified pipeline.

        Args:
            message: User message text.
            conversation_id: Conversation identifier.

        Returns:
            Composed assistant response.
        """
        settings = get_settings()
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

    def compose_and_persist(self, *, client: Any, source: ResponseSource) -> str:
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
        client: Any,
        message: str,
        conversation_id: str,
        history: list[Any],
    ) -> ResponseSource:
        timer_source = self.timer_handler.handle_direct_request(
            client=client,
            message=message,
            conversation_id=conversation_id,
            user_message=message,
        )
        if timer_source is not None:
            return timer_source

        pending_source = self._handle_pending_interaction(
            pending=pending_interactions.get(conversation_id),
            message=message,
            conversation_id=conversation_id,
            user_message=message,
        )
        if pending_source is not None:
            return pending_source

        decision = self.router.decide(message, client=client, history=history)
        if decision.mode == "interaction":
            if decision.interaction == "wipe":
                return self.wipe_handler.start(
                    conversation_id=conversation_id,
                    message=message,
                )
            note_source = self.note_handler.handle_direct_request(
                message=message,
                conversation_id=conversation_id,
                user_message=message,
            )
            if note_source is not None:
                return note_source

        if decision.mode == "tool":
            return self.tool_executor.run(
                user_message=message,
                conversation_id=conversation_id,
                tool_name=decision.tool_name or "",
                args=decision.tool_args,
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

        for handler in (
            self.timer_handler,
            self.note_handler,
            self.wipe_handler,
        ):
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

    def _finalize(self, *, client: Any, source: ResponseSource) -> str:
        content = self.composer.compose(client, source)
        if source.persist:
            repository.add_chat_message(
                conversation_id=source.conversation_id,
                role="assistant",
                content=content,
            )
        activity.standby(
            title="Nano is back in standby.",
            detail="The response is ready.",
            source="assistant.orchestrator",
        )
        return content
