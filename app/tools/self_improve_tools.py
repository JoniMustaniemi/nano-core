from __future__ import annotations

import json
from typing import Any

from app.llm.factory import get_llm_client
from app.memory.internal_note_service import internal_note_service
from app.proactive.store import proactive_store
from app.tools.base import ToolSpec
from app.tools.registry import register_tool
from app.tools.self_improve_service import SelfImproveResult, SelfImproveService


def _merge_preferred_files(*file_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in file_groups:
        for path in group:
            cleaned = str(path).strip()
            if cleaned and cleaned not in merged:
                merged.append(cleaned)
    return merged


def _propose_self_changes(args: dict[str, Any]) -> str:
    explicit_goal = str(args.get("goal", "")).strip()
    goal, internal_note_id, note_files = internal_note_service.resolve_self_improve_goal(explicit_goal)
    preferred_files = _merge_preferred_files(note_files, proactive_store.get_last_files())
    result = SelfImproveService().run(
        client=get_llm_client(),
        goal=goal,
        preferred_files=preferred_files or None,
    )
    if result.ok and internal_note_id is not None:
        internal_note_service.mark_delivered(internal_note_id)
    return _result_to_json(result, internal_note_id=internal_note_id)


def _result_to_json(result: SelfImproveResult, *, internal_note_id: int | None) -> str:
    payload = json.loads(result.to_json())
    if internal_note_id is not None:
        payload["internal_note_id"] = internal_note_id
    return json.dumps(payload, ensure_ascii=False)


register_tool(
    ToolSpec(
        name="propose_self_changes",
        description="analyze Nano's codebase, apply improvements under app/, verify, and open a pull request.",
        args_schema={"goal": "What to improve in Nano's own code."},
        handler=_propose_self_changes,
        announcement="Planning self-improvement changes.",
        keywords=("improve yourself", "fix yourself", "your code", "propose self"),
        ui_label="Propose self-improvement",
        ui_message="Improve yourself by making timer messages clearer.",
        ui_category="GitHub",
        ui_description="Analyze Nano's code and open a self-improvement PR.",
    )
)
