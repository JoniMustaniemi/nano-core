from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from app.assistant.prompts import AGENT_SYSTEM_PROMPT
from app.assistant.router import get_llm_client
from app.config import get_settings
from app.memory import repository
from app.runtime.activity import activity

AgentToolName = Literal[
    "run_python",
    "read_file",
    "write_file",
    "list_files",
    "add_note",
    "list_notes",
    "add_reminder",
    "list_reminders",
]


@dataclass(slots=True)
class ToolResult:
    tool: str
    content: str


class AgentService:
    def respond(self, message: str, conversation_id: str = "default") -> str:
        settings = get_settings()
        repository.add_chat_message(conversation_id=conversation_id, role="user", content=message)

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self._system_prompt(),
            }
        ]

        history = repository.list_chat_messages(
            conversation_id=conversation_id,
            limit=settings.chat_history_limit,
        )
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

    def _system_prompt(self) -> str:
        return AGENT_SYSTEM_PROMPT + "\n\n" + self._tool_list()

    def _tool_list(self) -> str:
        return (
            "Available tools:\n"
            "- run_python(code): execute local Python code and return stdout/stderr.\n"
            "- read_file(path): read a text file under the workspace root.\n"
            "- write_file(path, content): write a text file under the workspace root.\n"
            "- list_files(path): list files under the workspace root.\n"
            "- add_note(content): save a note.\n"
            "- list_notes(): list recent notes.\n"
            "- add_reminder(content, due_at): save a reminder.\n"
            "- list_reminders(): list reminders.\n"
            "Return JSON only in one of these forms:\n"
            '{"type":"final","content":"..."}\n'
            '{"type":"tool_call","tool":"run_python","args":{"code":"..."} }\n'
        )

    def _parse_decision(self, raw: str) -> dict[str, Any]:
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
        if tool_name == "run_python":
            return ToolResult(tool=tool_name, content=self._run_python(args))
        if tool_name == "read_file":
            return ToolResult(tool=tool_name, content=self._read_file(args))
        if tool_name == "write_file":
            return ToolResult(tool=tool_name, content=self._write_file(args))
        if tool_name == "list_files":
            return ToolResult(tool=tool_name, content=self._list_files(args))
        if tool_name == "add_note":
            content = str(args.get("content", ""))
            note = repository.add_note(content)
            return ToolResult(tool=tool_name, content=f"saved note {note.id}: {note.content}")
        if tool_name == "list_notes":
            notes = repository.list_notes()
            rendered = "\n".join(f"{note.id}: {note.content}" for note in notes) or "No notes."
            return ToolResult(tool=tool_name, content=rendered)
        if tool_name == "add_reminder":
            content = str(args.get("content", ""))
            due_at_raw = str(args.get("due_at", ""))
            due_at = datetime.fromisoformat(due_at_raw)
            reminder = repository.add_reminder(content, due_at)
            return ToolResult(
                tool=tool_name,
                content=f"saved reminder {reminder.id}: {reminder.content}",
            )
        if tool_name == "list_reminders":
            reminders = repository.list_reminders()
            rendered = "\n".join(
                f"{reminder.id}: {reminder.content} @ {reminder.due_at.isoformat()}"
                for reminder in reminders
            ) or "No reminders."
            return ToolResult(tool=tool_name, content=rendered)
        return ToolResult(tool=tool_name, content=f"Unknown tool: {tool_name}")

    def _workspace_root(self) -> Path:
        settings = get_settings()
        return Path(settings.workspace_root).resolve()

    def _resolve_workspace_path(self, raw_path: str) -> Path:
        workspace = self._workspace_root()
        path = (workspace / raw_path).resolve()
        if workspace not in path.parents and path != workspace:
            raise ValueError("Path must stay within the workspace root.")
        return path

    def _run_python(self, args: dict[str, Any]) -> str:
        code = str(args.get("code", ""))
        timeout_seconds = int(args.get("timeout_seconds", 30))
        workspace = self._workspace_root()
        process = subprocess.run(
            [sys.executable, "-c", code],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return self._format_process_output(process.returncode, process.stdout, process.stderr)

    def _read_file(self, args: dict[str, Any]) -> str:
        path = self._resolve_workspace_path(str(args.get("path", "")))
        return path.read_text(encoding="utf-8")

    def _write_file(self, args: dict[str, Any]) -> str:
        path = self._resolve_workspace_path(str(args.get("path", "")))
        content = str(args.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"wrote {path}"

    def _list_files(self, args: dict[str, Any]) -> str:
        path = self._resolve_workspace_path(str(args.get("path", ".")))
        if not path.exists():
            return f"{path} does not exist"
        entries = sorted(item.name for item in path.iterdir())
        return "\n".join(entries) or "(empty)"

    def _format_process_output(self, returncode: int, stdout: str, stderr: str) -> str:
        parts = [f"exit code: {returncode}"]
        if stdout.strip():
            parts.append(f"stdout:\n{stdout.strip()}")
        if stderr.strip():
            parts.append(f"stderr:\n{stderr.strip()}")
        return "\n".join(parts)
