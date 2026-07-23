from __future__ import annotations

import json
from typing import Any

from app.llm.factory import get_llm_client
from app.memory.internal_note_service import internal_note_service
from app.proactive.store import proactive_store
from app.tools.base import ToolSpec
from app.tools.improvement_plan_service import ImprovementPlanResult, ImprovementPlanService
from app.tools.registry import register_tool


def _merge_preferred_files(*file_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in file_groups:
        for path in group:
            cleaned = str(path).strip()
            if cleaned and cleaned not in merged:
                merged.append(cleaned)
    return merged


def _draft_improvement_plan(args: dict[str, Any]) -> str:
    explicit_goal = str(args.get("goal", "")).strip()
    goal, internal_note_id, note_files = internal_note_service.resolve_self_improve_goal(explicit_goal)
    preferred_files = _merge_preferred_files(note_files, proactive_store.get_last_files())
    result = ImprovementPlanService().draft(
        client=get_llm_client(),
        goal=goal,
        preferred_files=preferred_files or None,
        source_note_id=internal_note_id,
    )
    if result.ok and internal_note_id is not None:
        internal_note_service.mark_delivered(internal_note_id)
    return _result_to_json(result, internal_note_id=internal_note_id)


def _result_to_json(result: ImprovementPlanResult, *, internal_note_id: int | None) -> str:
    payload = {
        "ok": result.ok,
        "step": result.step,
        "plan_id": result.plan_id,
        "title": result.title,
        "goal": result.goal,
        "error": result.error,
    }
    if internal_note_id is not None:
        payload["internal_note_id"] = internal_note_id
    return json.dumps(payload, ensure_ascii=False)


register_tool(
    ToolSpec(
        name="draft_improvement_plan",
        description="Draft a text improvement plan for Nano's own codebase without applying changes.",
        args_schema={"goal": "What to improve in Nano's own code."},
        handler=_draft_improvement_plan,
        announcement="Drafting an improvement plan.",
        keywords=("improve yourself", "fix yourself", "your code", "draft plan"),
        ui_label="Draft improvement plan",
        ui_message="Draft an improvement plan for clearer timer messages.",
        ui_category="Self-improvement",
        ui_description="Draft a readable text plan for a self-improvement idea.",
    )
)
