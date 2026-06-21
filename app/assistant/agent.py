from __future__ import annotations

import json
from typing import Any, cast

from app.assistant.agent_rules import (
    duration_args_from_message,
    is_confirmation_message,
    is_health_check_request,
    is_rejection_message,
    is_timer_cancel_request,
    is_timer_start_request,
    is_timer_status_request,
    needs_timer_duration,
    needs_wipe_confirmation,
    parse_decision,
    should_answer_without_tools,
    timer_confirmation,
    tool_matches_request,
    tool_signature,
    wipe_confirmation_prompt,
)
from app.assistant.agent_types import ToolResult
from app.assistant.pending import PendingInteraction, pending_interactions
from app.assistant.prompts import (
    AGENT_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    WIPE_CONFIRMATION_SYSTEM_PROMPT,
)
from app.assistant.result_summarizer import ToolResultSummarizer
from app.assistant.router import get_llm_client
from app.assistant.tool_runner import ToolRunner
from app.config import get_settings
from app.memory import repository
from app.runtime.activity import activity
from app.tools import render_tool_prompt


class AgentService:
    def __init__(
        self,
        *,
        tool_runner: ToolRunner | None = None,
        summarizer: ToolResultSummarizer | None = None,
    ) -> None:
        self.tool_runner = tool_runner or ToolRunner()
        self.summarizer = summarizer or ToolResultSummarizer()

    def respond(self, message: str, conversation_id: str = "default") -> str:
        settings = get_settings()
        repository.add_chat_message(conversation_id=conversation_id, role="user", content=message)

        history = repository.list_chat_messages(
            conversation_id=conversation_id,
            limit=settings.chat_history_limit,
        )
        messages = self._build_agent_messages(history=history, message=message)
        client = get_llm_client()
        direct_response = self._handle_direct_request(
            client=client,
            conversation_id=conversation_id,
            message=message,
            history=history,
        )
        if direct_response is not None:
            return direct_response

        return self._run_planned_response(
            client=client,
            conversation_id=conversation_id,
            message=message,
            history=history,
            messages=messages,
        )

    def _build_agent_messages(
        self,
        *,
        history: list[Any],
        message: str,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": self._system_prompt()}]
        for entry in history:
            messages.append({"role": entry.role, "content": entry.content})
        if not history or history[-1].role != "user" or history[-1].content != message:
            messages.append({"role": "user", "content": message})
        return messages

    def _handle_direct_request(
        self,
        *,
        client: Any,
        conversation_id: str,
        message: str,
        history: list[Any],
    ) -> str | None:
        if is_timer_status_request(message):
            pending_interactions.clear(conversation_id)
            return self._run_direct_tool(
                client=client,
                conversation_id=conversation_id,
                user_message=message,
                tool_name="list_timers",
                args={},
            )

        if is_timer_cancel_request(message):
            pending_interactions.clear(conversation_id)
            return self._run_direct_tool(
                client=client,
                conversation_id=conversation_id,
                user_message=message,
                tool_name="cancel_timers",
                args={},
            )

        pending_response = self._handle_pending_interaction(
            pending=pending_interactions.get(conversation_id),
            message=message,
            conversation_id=conversation_id,
        )
        if pending_response is not None:
            return pending_response

        if needs_wipe_confirmation(message):
            return self._start_wipe_confirmation(
                client=client,
                conversation_id=conversation_id,
                message=message,
            )

        if needs_timer_duration(message):
            return self._request_timer_duration(
                conversation_id=conversation_id,
                message=message,
            )

        if is_timer_start_request(message):
            duration_args = duration_args_from_message(message)
            if duration_args is not None:
                return self._run_timer_request(
                    conversation_id=conversation_id,
                    args=duration_args,
                )

        if is_health_check_request(message):
            return self._run_direct_tool(
                client=client,
                conversation_id=conversation_id,
                user_message=message,
                tool_name="check_health",
                args={},
                summarize_result=True,
            )

        if should_answer_without_tools(message):
            return self._fallback_to_chat(
                client=client,
                message=message,
                conversation_id=conversation_id,
                history=history,
            )

        return None

    def _start_wipe_confirmation(
        self,
        *,
        client: Any,
        conversation_id: str,
        message: str,
    ) -> str:
        confirmation_prompt = self._build_wipe_confirmation_prompt(
            client=client,
            message=message,
        )
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="wipe_confirmation",
            payload={"request": message},
        )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=confirmation_prompt,
        )
        activity.standby(
            title="Nano needs confirmation.",
            detail="Waiting for confirmation before wiping the database.",
            source="assistant.agent",
        )
        return confirmation_prompt

    def _request_timer_duration(self, *, conversation_id: str, message: str) -> str:
        follow_up = "How long should the timer run?"
        pending_interactions.set(
            conversation_id=conversation_id,
            kind="timer_duration",
            payload={"request": message},
        )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=follow_up,
        )
        activity.standby(
            title="Nano needs one detail.",
            detail="Waiting for the timer duration.",
            source="assistant.agent",
        )
        return follow_up

    def _run_planned_response(
        self,
        *,
        client: Any,
        conversation_id: str,
        message: str,
        history: list[Any],
        messages: list[dict[str, str]],
    ) -> str:
        activity.working(
            title="Nano is planning an action.",
            detail="Using the local model to decide whether to answer or run a tool.",
            source="assistant.agent",
        )

        invalid_json_attempts = 0
        executed_tools: dict[str, ToolResult] = {}
        for _ in range(8):
            raw = client.complete(messages=messages)
            decision = parse_decision(raw)

            if decision["type"] == "final":
                return self._finish_planned_response(
                    conversation_id=conversation_id,
                    content=decision["content"],
                )

            if decision["type"] != "tool_call":
                invalid_json_attempts += 1
                if invalid_json_attempts >= 2:
                    return self._fallback_to_chat(
                        client=client,
                        message=message,
                        conversation_id=conversation_id,
                        history=history,
                    )
                self._append_model_correction(
                    messages=messages,
                    raw=raw,
                    content="The previous response was not valid JSON. Return only a JSON object.",
                )
                continue

            tool_name = decision["tool"]
            args = decision["args"]
            if not tool_matches_request(message, tool_name):
                self._append_model_correction(
                    messages=messages,
                    raw=raw,
                    content=(
                        f"The tool call {tool_name} does not match the user's request. "
                        "Do not call a tool here. Return a final answer directly."
                    ),
                )
                continue

            signature = tool_signature(tool_name, args)
            existing_result = executed_tools.get(signature)
            if existing_result is not None:
                self._append_model_correction(
                    messages=messages,
                    raw=raw,
                    content=(
                        f"Tool {tool_name} was already called with the same arguments and "
                        f"returned:\n{existing_result.content}\n"
                        "Do not call the same tool again. Return a final answer now."
                    ),
                )
                continue

            activity.log(
                title=f"Nano called {tool_name}.",
                detail=json.dumps(args, ensure_ascii=False),
                source="assistant.agent",
            )
            self.tool_runner.announce_call(tool_name)
            result = self.tool_runner.execute(tool_name, args)
            executed_tools[signature] = result
            self._append_model_result(messages=messages, raw=raw, result=result)

        fallback = "I tried to complete the task, but I hit the step limit."
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=fallback,
        )
        self.tool_runner.report_error(
            title="Nano could not finish the task.",
            detail=fallback,
            spoken_message="I could not finish the task.",
        )
        return fallback

    def _append_model_correction(
        self,
        *,
        messages: list[dict[str, str]],
        raw: str,
        content: str,
    ) -> None:
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "system", "content": content})

    def _append_model_result(
        self,
        *,
        messages: list[dict[str, str]],
        raw: str,
        result: ToolResult,
    ) -> None:
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Tool {result.tool} returned:\n{result.content}\n"
                    "Use that result to continue or answer."
                ),
            }
        )

    def _finish_planned_response(self, *, conversation_id: str, content: str) -> str:
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
        )
        activity.standby(
            title="Nano finished the task.",
            detail="The agent returned a final response.",
            source="assistant.agent",
        )
        return content

    def _fallback_to_chat(
        self,
        *,
        client: Any,
        message: str,
        conversation_id: str,
        history: list[Any],
    ) -> str:
        fallback_messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        for entry in history:
            fallback_messages.append({"role": entry.role, "content": entry.content})
        if not history or history[-1].role != "user" or history[-1].content != message:
            fallback_messages.append({"role": "user", "content": message})

        content = cast(str, client.complete(messages=fallback_messages))
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
        )
        activity.standby(
            title="Nano answered without tools.",
            detail="The local model could not follow agent JSON, so Nano used plain chat mode.",
            source="assistant.agent",
        )
        return content

    def _system_prompt(self) -> str:
        return AGENT_SYSTEM_PROMPT + "\n\n" + self._tool_list()

    def _tool_list(self) -> str:
        return render_tool_prompt()

    def _run_direct_tool(
        self,
        *,
        client: Any,
        conversation_id: str,
        user_message: str,
        tool_name: str,
        args: dict[str, Any],
        summarize_result: bool = False,
    ) -> str:
        activity.log(
            title=f"Nano called {tool_name}.",
            detail=json.dumps(args, ensure_ascii=False),
            source="assistant.agent",
        )
        self.tool_runner.announce_call(tool_name)
        result = self.tool_runner.execute(tool_name, args)
        activity.log(
            title=f"Tool {tool_name} returned.",
            detail=result.content,
            source="assistant.agent",
        )
        content = result.content
        if summarize_result:
            content = self.summarizer.summarize(
                client=client,
                user_message=user_message,
                tool_name=tool_name,
                tool_result=result.content,
            )
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
        )
        activity.standby(
            title="Nano finished the task.",
            detail=f"{tool_name} completed.",
            source="assistant.agent",
        )
        return content

    def _build_wipe_confirmation_prompt(self, *, client: Any, message: str) -> str:
        prompt_messages = [
            {"role": "system", "content": WIPE_CONFIRMATION_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]
        draft = cast(str, client.complete(messages=prompt_messages)).strip()
        if not draft:
            return wipe_confirmation_prompt(message)
        cleaned = draft.replace("\n", " ").strip()
        cleaned = cleaned.rstrip(". ")
        return f"{cleaned}. Reply yes to proceed or no to cancel."

    def _handle_pending_interaction(
        self,
        *,
        pending: PendingInteraction | None,
        message: str,
        conversation_id: str,
    ) -> str | None:
        if pending is None:
            return None

        if pending.kind == "timer_duration":
            return self._complete_pending_timer_request(
                message=message,
                conversation_id=conversation_id,
            )

        if pending.kind == "wipe_confirmation":
            return self._handle_pending_wipe_confirmation(
                message=message,
                conversation_id=conversation_id,
            )

        pending_interactions.clear(conversation_id)
        return None

    def _complete_pending_timer_request(
        self,
        *,
        message: str,
        conversation_id: str,
    ) -> str | None:
        duration_args = duration_args_from_message(message)
        if duration_args is None:
            follow_up = "Specify the timer duration in seconds or minutes."
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=follow_up,
            )
            activity.standby(
                title="Nano needs one detail.",
                detail="Waiting for a valid timer duration.",
                source="assistant.agent",
            )
            return follow_up

        pending_interactions.clear(conversation_id)
        return self._run_timer_request(
            conversation_id=conversation_id,
            args=duration_args,
        )

    def _run_timer_request(
        self,
        *,
        conversation_id: str,
        args: dict[str, Any],
    ) -> str:
        activity.log(
            title="Nano called start_timer.",
            detail=json.dumps(args, ensure_ascii=False),
            source="assistant.agent",
        )
        self.tool_runner.announce_call("start_timer")
        result = self.tool_runner.execute("start_timer", args)
        confirmation = timer_confirmation(args)
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=confirmation,
        )
        activity.standby(
            title="Nano finished the task.",
            detail=result.content,
            source="assistant.agent",
        )
        return confirmation

    def _handle_pending_wipe_confirmation(
        self,
        *,
        message: str,
        conversation_id: str,
    ) -> str | None:
        if is_rejection_message(message):
            response = "Database wipe cancelled."
            pending_interactions.clear(conversation_id)
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
            activity.standby(
                title="Nano cancelled the wipe.",
                detail="The database was left intact.",
                source="assistant.agent",
            )
            return response

        if not is_confirmation_message(message):
            response = "Reply yes to confirm the database wipe, or no to cancel."
            repository.add_chat_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response,
            )
            activity.standby(
                title="Nano still needs confirmation.",
                detail="Waiting for a clear yes or no before wiping the database.",
                source="assistant.agent",
            )
            return response

        repository.wipe_database()
        pending_interactions.clear(conversation_id)
        response = "Database wiped."
        activity.standby(
            title="Nano wiped the database.",
            detail="Notes, reminders, and chat history were deleted.",
            source="assistant.agent",
        )
        return response
