from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from app.assistant.rules.parsing import extract_json
from app.config import Settings, get_settings
from app.memory import codebase_index
from app.proactive.codebase_files import list_all_app_files
from app.runtime.activity import activity

_LLM_UNAVAILABLE_MARKERS = (
    "Local LLM is not available yet",
    "LLM_MODEL_PATH",
)
SELECT_JSON_HINT = '{"files_to_read": ["app/..."]}'
PLAN_JSON_HINT = '{"path": "app/...", "content": "..."}'
PATCH_JSON_HINT = '{"path": "app/...", "old_text": "...", "new_text": "..."}'
PLAN_TEMPERATURE = 0.1
PATCH_CORRECTIONS: dict[str, str] = {
    "invalid_json": (
        "Your previous response was invalid JSON. Return JSON only with path, old_text, and new_text. "
        f"Example: {PATCH_JSON_HINT}"
    ),
    "wrong_path": (
        "Your previous response used the wrong path. Return JSON only for the requested file path with "
        "old_text and new_text. "
        f"Example: {PATCH_JSON_HINT}"
    ),
    "empty_old_text": (
        "Your previous response omitted old_text. Copy the exact snippet to replace from the provided "
        "source. "
        f"Example: {PATCH_JSON_HINT}"
    ),
    "old_text_not_found": (
        "old_text was not found verbatim in the file. Copy the exact snippet from the provided source, "
        "including quotes and whitespace. "
        f"Example: {PATCH_JSON_HINT}"
    ),
}
GOAL_FILE_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("timer", "timers"), "app/assistant/flows/timer.py"),
    (("timer", "timers", "message", "messages", "status", "wording", "clearer", "copy"), "app/runtime/status_copy.py"),
    (("wake", "greeting", "ack"), "app/runtime/status_copy.py"),
    (("note", "notes"), "app/assistant/flows/note.py"),
    (("health",), "app/health/checks.py"),
    (("pull request", "pr", "github"), "app/tools/pr_service.py"),
)


def looks_like_llm_unavailable(raw: str) -> bool:
    return any(marker in raw for marker in _LLM_UNAVAILABLE_MARKERS)


def plan_max_tokens(content: str, *, settings: Settings) -> int:
    estimated = len(content) // 2 + 512
    return min(
        max(estimated, settings.llm_max_tokens),
        settings.self_improve_plan_max_tokens,
    )


@dataclass(frozen=True, slots=True)
class PatchParseResult:
    parsed: dict[str, str] | None = None
    reason: str | None = None


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


def parse_patch_change(
    payload: dict[str, Any],
    *,
    expected_path: str,
    allowed: str,
    original_content: str,
) -> PatchParseResult:
    parsed = parse_single_file_change(
        payload,
        expected_path=expected_path,
        allowed=allowed,
    )
    if parsed is not None:
        return PatchParseResult(parsed=parsed)

    allowed_prefix = allowed.rstrip("/")
    path = str(payload.get("path", "")).strip()
    old_text = str(payload.get("old_text", payload.get("search", "")))
    new_text = str(payload.get("new_text", payload.get("replace", "")))
    if not path or path != expected_path or not path.startswith(allowed_prefix):
        return PatchParseResult(reason="wrong_path")
    if not old_text:
        return PatchParseResult(reason="empty_old_text")
    if old_text not in original_content:
        return PatchParseResult(reason="old_text_not_found")
    return PatchParseResult(
        parsed={
            "path": path,
            "content": original_content.replace(old_text, new_text, 1),
        }
    )


def parse_single_file_change(
    payload: dict[str, Any],
    *,
    expected_path: str,
    allowed: str,
) -> dict[str, str] | None:
    allowed_prefix = allowed.rstrip("/")
    path = str(payload.get("path", "")).strip()
    content = str(payload.get("content", ""))
    if path and content and path.startswith(allowed_prefix):
        return {"path": path, "content": content}

    changes = payload.get("changes")
    if isinstance(changes, list):
        for item in changes:
            if not isinstance(item, dict):
                continue
            item_path = str(item.get("path", "")).strip()
            item_content = str(item.get("content", ""))
            if item_path == expected_path and item_content and item_path.startswith(allowed_prefix):
                return {"path": item_path, "content": item_content}
    return None


def patch_correction_for_reason(reason: str | None) -> str:
    if reason and reason in PATCH_CORRECTIONS:
        return PATCH_CORRECTIONS[reason]
    return PATCH_CORRECTIONS["invalid_json"]


def plan_single_file_change(
    client: Any,
    *,
    goal: str,
    path: str,
    content: str,
    allowed: str,
) -> dict[str, str] | None:
    settings = get_settings()
    patch_max_tokens = min(2048, plan_max_tokens(content, settings=settings))
    full_max_tokens = plan_max_tokens(content, settings=settings)
    last_reason: str | None = None

    patch_messages = [
        {
            "role": "system",
            "content": (
                "You edit one Python source file for a self-improvement task. "
                f"Return JSON only: {PATCH_JSON_HINT} "
                "Use old_text copied exactly from the file and new_text as the replacement. "
                "Keep the JSON small. No markdown fences."
            ),
        },
        {
            "role": "user",
            "content": f"Goal: {goal}\n\n### {path}\n{content}",
        },
    ]
    for _attempt in range(3):
        raw = cast(
            str,
            client.complete(
                messages=patch_messages,
                max_tokens=patch_max_tokens,
                temperature=PLAN_TEMPERATURE,
            ),
        ).strip()
        if looks_like_llm_unavailable(raw):
            return None
        payload = extract_json(raw)
        if isinstance(payload, dict):
            result = parse_patch_change(
                payload,
                expected_path=path,
                allowed=allowed,
                original_content=content,
            )
            if result.parsed is not None:
                return result.parsed
            last_reason = result.reason
            patch_correction = patch_correction_for_reason(result.reason)
        else:
            last_reason = "invalid_json"
            patch_correction = PATCH_CORRECTIONS["invalid_json"]
        patch_messages.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": patch_correction},
            ]
        )

    full_messages = [
        {
            "role": "system",
            "content": (
                "You edit one Python source file for a self-improvement task. "
                f"Return JSON only: {PLAN_JSON_HINT} "
                "where content is the complete updated file. "
                "Use \\n for newlines inside the JSON string. No markdown fences."
            ),
        },
        {
            "role": "user",
            "content": f"Goal: {goal}\n\n### {path}\n{content}",
        },
    ]
    full_correction = (
        "Your previous response was invalid. Return JSON only with keys path and content. "
        f"Example: {PLAN_JSON_HINT}"
    )
    for _attempt in range(2):
        raw = cast(
            str,
            client.complete(
                messages=full_messages,
                max_tokens=full_max_tokens,
                temperature=PLAN_TEMPERATURE,
            ),
        ).strip()
        if looks_like_llm_unavailable(raw):
            return None
        payload = extract_json(raw)
        if isinstance(payload, dict):
            parsed = parse_single_file_change(
                payload,
                expected_path=path,
                allowed=allowed,
            )
            if parsed is not None:
                return parsed
            last_reason = "invalid_json"
        else:
            last_reason = "invalid_json"
        full_messages.extend(
            [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": full_correction},
            ]
        )

    activity.log(
        title="Self-improve plan failed",
        detail=f"{path}: {last_reason or 'unknown'}",
        source="tools.self_improve_service",
    )
    return None


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
