from __future__ import annotations

from typing import Any

from app.memory.labels import InvalidTimerLabelError, normalize_timer_label
from app.memory.models import Timer
from app.tools.errors import ToolError


def normalize_label(raw: str, default: str) -> str:
    try:
        return normalize_timer_label(raw, default)
    except InvalidTimerLabelError as exc:
        raise ToolError(str(exc)) from exc


def resolve_rename_target(
    items: list[Timer],
    *,
    item_id: Any,
    old_label: str,
    item_noun: str,
) -> Timer:
    if item_id not in (None, ""):
        try:
            requested_id = int(item_id)
        except (TypeError, ValueError) as exc:
            raise ToolError(f"Invalid {item_noun} id.") from exc
        for item in items:
            if item.id == requested_id:
                return item
        raise ToolError(f"No matching active {item_noun} to rename.")

    if old_label:
        matches = [item for item in items if str(item.label).strip().lower() == old_label.lower()]
        if not matches:
            raise ToolError(f"No matching active {item_noun} to rename.")
        if len(matches) > 1:
            raise ToolError(f'Multiple {item_noun}s labeled "{old_label}". Specify {item_noun} id.')
        return matches[0]

    raise ToolError(f"Specify which {item_noun} to rename.")


def timer_matches_cancel_request(
    timer_id: int | None,
    timer_label: str,
    requested_id: Any,
    requested_label: str,
) -> bool:
    if requested_id in (None, "") and not requested_label:
        return True
    if requested_id not in (None, ""):
        try:
            if timer_id == int(requested_id):
                return True
        except (TypeError, ValueError):
            return False
    return bool(requested_label and timer_label.lower() == requested_label)
