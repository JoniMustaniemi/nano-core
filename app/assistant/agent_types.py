from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, NotRequired, TypedDict

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
    "cancel_timers",
    "check_health",
    "create_pull_request",
]


@dataclass(slots=True)
class ToolResult:
    tool: str
    content: str
    ok: bool = True


class AnswerIntentDecision(TypedDict):
    type: Literal["answer_intent"]
    content: NotRequired[str]


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


Decision = AnswerIntentDecision | FinalDecision | ToolCallDecision | InvalidDecision
