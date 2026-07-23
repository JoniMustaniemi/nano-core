from __future__ import annotations

from typing import Any, cast

from app.assistant.rules.parsing import extract_json
from app.memory import codebase_index
from app.proactive.codebase_files import list_all_app_files

_LLM_UNAVAILABLE_MARKERS = (
    "Local LLM is not available yet",
    "LLM_MODEL_PATH",
)
SELECT_JSON_HINT = '{"files_to_read": ["app/..."]}'
GOAL_FILE_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("timer", "timers"), "app/assistant/flows/timer.py"),
    (("timer", "timers", "message", "messages", "status", "wording", "clearer", "copy"), "app/runtime/status_copy.py"),
    (("wake", "greeting", "ack"), "app/runtime/status_copy.py"),
    (("message", "messages", "confirmation", "wipe", "note"), "app/assistant/rules/messages.py"),
    (("note", "notes"), "app/assistant/flows/note.py"),
    (("health",), "app/health/checks.py"),
    (("pull request", "pr", "github"), "app/tools/pr_service.py"),
)


def looks_like_llm_unavailable(raw: str) -> bool:
    return any(marker in raw for marker in _LLM_UNAVAILABLE_MARKERS)


def complete_json_dict(
    client: Any,
    messages: list[dict[str, str]],
    *,
    correction: str,
    attempts: int = 2,
) -> dict[str, Any] | None:
    conversation = list(messages)
    for _attempt in range(attempts):
        raw = cast(str, client.complete(messages=conversation)).strip()
        if looks_like_llm_unavailable(raw):
            return None
        payload = extract_json(raw)
        if isinstance(payload, dict):
            return payload
        conversation.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": correction},
            ]
        )
    return None


def parse_selection(payload: dict[str, Any]) -> list[str]:
    files_to_read = payload.get("files_to_read", [])
    if not isinstance(files_to_read, list):
        return []
    return [str(path) for path in files_to_read if str(path).strip()]


def fallback_files_for_goal(goal: str, *, allowed: str) -> list[str]:
    lowered = goal.lower()
    allowed_prefix = allowed.rstrip("/")
    matched: list[str] = []
    for keywords, path in GOAL_FILE_HINTS:
        if any(keyword in lowered for keyword in keywords):
            if path.startswith(allowed_prefix) and path not in matched:
                matched.append(path)
    return matched


def file_selection_lines(goal: str, *, limit: int = 40) -> list[str]:
    records = codebase_index.list_records_for_selection(limit=limit)
    if records:
        lines = [f"- {record.path}: {record.summary}" for record in records if record.summary]
        if lines:
            return lines

    all_paths = list_all_app_files()
    codebase_index.sync_paths(all_paths)
    keywords = [word.lower() for word in goal.split() if len(word) > 3]
    if keywords:
        matched = [
            path
            for path in all_paths
            if any(keyword in path.lower() for keyword in keywords)
        ]
        if matched:
            return [f"- {path}: (not yet scanned)" for path in matched[:limit]]

    return [f"- {path}: (not yet scanned)" for path in all_paths[:limit]]
