from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, NotRequired, TypedDict, cast

from app.assistant.prompts import AGENT_SYSTEM_PROMPT, SYSTEM_PROMPT
from app.assistant.router import get_llm_client
from app.config import get_settings
from app.memory import repository
from app.runtime.activity import activity
from app.tools import get_tool, list_tools, render_tool_prompt

AgentToolName = Literal[
    "run_python",
    "read_file",
    "write_file",
    "list_files",
    "add_note",
    "list_notes",
    "add_reminder",
    "list_reminders",
    "start_timer",
    "list_timers",
]


@dataclass(slots=True)
class ToolResult:
    tool: str
    content: str


class FinalDecision(TypedDict):
    type: Literal["final"]
    content: str


class ToolCallDecision(TypedDict):
    type: Literal["tool_call"]
    tool: str
    args: dict[str, Any]


class InvalidDecision(TypedDict):
    type: Literal["invalid"]
    content: NotRequired[str]
    tool: NotRequired[str]
    args: NotRequired[dict[str, Any]]


Decision = FinalDecision | ToolCallDecision | InvalidDecision


class AgentService:
    def respond(self, message: str, conversation_id: str = "default") -> str:
        settings = get_settings()
        repository.add_chat_message(conversation_id=conversation_id, role="user", content=message)

        history = repository.list_chat_messages(
            conversation_id=conversation_id,
            limit=settings.chat_history_limit,
        )
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self._system_prompt(),
            }
        ]

        for entry in history:
            messages.append({"role": entry.role, "content": entry.content})

        if not history or history[-1].role != "user" or history[-1].content != message:
            messages.append({"role": "user", "content": message})

        client = get_llm_client()
        activity.working(
            title="Nano is planning an action.",
            detail="Using the local model to decide whether to answer or run a tool.",
            source="assistant.agent",
        )

        invalid_json_attempts = 0
        for _ in range(8):
            raw = client.complete(messages=messages)
            decision = self._parse_decision(raw)

            if decision["type"] == "final":
                content = decision["content"]
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

            if decision["type"] != "tool_call":
                invalid_json_attempts += 1
                if invalid_json_attempts >= 2:
                    return self._fallback_to_chat(
                        client=client,
                        message=message,
                        conversation_id=conversation_id,
                        history=history,
                    )
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "The previous response was not valid JSON. "
                            "Return only a JSON object."
                        ),
                    }
                )
                continue

            tool_name = decision["tool"]
            args = decision["args"]
            activity.log(
                title=f"Nano called {tool_name}.",
                detail=json.dumps(args, ensure_ascii=False),
                source="assistant.agent",
            )
            result = self._execute_tool(tool_name, args)
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

        fallback = "I tried to complete the task, but I hit the step limit."
        repository.add_chat_message(
            conversation_id=conversation_id,
            role="assistant",
            content=fallback,
        )
        activity.error(
            title="Nano could not finish the task.",
            detail=fallback,
            source="assistant.agent",
        )
        return fallback

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

    def _parse_decision(self, raw: str) -> Decision:
        payload = self._extract_json(raw)
        if isinstance(payload, dict):
            decision_type = payload.get("type")
            if decision_type == "final" and isinstance(payload.get("content"), str):
                return {"type": "final", "content": payload["content"]}
            if decision_type == "tool_call":
                tool = payload.get("tool")
                args = payload.get("args", {})
                if isinstance(tool, str) and isinstance(args, dict):
                    return {"type": "tool_call", "tool": tool, "args": args}
        return {"type": "invalid"}

    def _extract_json(self, raw: str) -> Any:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        tool = get_tool(tool_name)
        if tool is None:
            available = ", ".join(tool_spec.name for tool_spec in list_tools())
            return ToolResult(
                tool=tool_name,
                content=f"Unknown tool: {tool_name}. Available tools: {available}",
            )
        return ToolResult(tool=tool_name, content=tool.handler(args))
