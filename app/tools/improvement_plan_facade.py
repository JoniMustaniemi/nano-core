from __future__ import annotations

import json
from dataclasses import dataclass

from app.common.types import ProactiveOffer
from app.memory import improvement_plans, internal_notes
from app.memory.improvement_plans import files_from_plan
from app.memory.models import ImprovementPlan, InternalNote
from app.runtime.background import run_background
from app.tools.improvement_plan_implementation import (
    ImprovementPlanImplementationService,
    check_implementation_preflight,
)


@dataclass(frozen=True, slots=True)
class ImprovementPlanSummary:
    id: int
    title: str
    goal: str
    status: str
    files: list[str]
    created_at: str
    kind: str = "drafted"
    processed_at: str | None = None


@dataclass(frozen=True, slots=True)
class ImprovementPlanDetail:
    id: int
    title: str
    goal: str
    status: str
    kind: str
    files: list[str]
    created_at: str
    processed_at: str | None
    body: str


@dataclass(frozen=True, slots=True)
class ImplementPlanResult:
    ok: bool
    plan_id: int
    status: str


def parse_files(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    files: list[str] = []
    for path in raw:
        cleaned = str(path).strip()
        if cleaned and cleaned not in files:
            files.append(cleaned)
    return files


def _goal_from_note(note: InternalNote) -> str:
    try:
        offer = ProactiveOffer.from_json(note.payload_json)
    except json.JSONDecodeError:
        return note.content.strip()
    goal = str(offer.payload.get("goal", "")).strip()
    if goal:
        return goal
    return offer.summary.strip() or note.content.strip()


def _files_from_note(note: InternalNote) -> list[str]:
    try:
        offer = ProactiveOffer.from_json(note.payload_json)
    except json.JSONDecodeError:
        return []
    return parse_files(offer.payload.get("files", []))


def _suggestion_body(note: InternalNote) -> str:
    try:
        offer = ProactiveOffer.from_json(note.payload_json)
    except json.JSONDecodeError:
        return note.content.strip()

    sections: list[str] = []
    summary = offer.summary.strip()
    goal = str(offer.payload.get("goal", "")).strip()
    if summary:
        sections.append(summary)
    if goal and goal != summary:
        sections.append(f"Goal: {goal}")
    content = note.content.strip()
    if content and content not in {summary, goal}:
        sections.append(content)
    files = _files_from_note(note)
    if files:
        sections.append("Files:\n" + "\n".join(f"- {path}" for path in files))
    sections.append(
        "Nano will ask if you are there when idle, then draft a readable plan from this topic."
    )
    return "\n\n".join(section for section in sections if section)


def _to_summary(plan: ImprovementPlan) -> ImprovementPlanSummary:
    if plan.id is None:
        raise ValueError("Plan must have an id")
    return ImprovementPlanSummary(
        id=plan.id,
        title=plan.title,
        goal=plan.goal,
        status=plan.status,
        kind="drafted",
        files=files_from_plan(plan),
        created_at=plan.created_at.isoformat(),
        processed_at=plan.processed_at.isoformat() if plan.processed_at else None,
    )


def _suggestion_summary(note: InternalNote) -> ImprovementPlanSummary:
    if note.id is None:
        raise ValueError("Suggestion must have an id")
    return ImprovementPlanSummary(
        id=note.id,
        title=note.title,
        goal=_goal_from_note(note),
        status="waiting",
        kind="suggestion",
        files=_files_from_note(note),
        created_at=note.created_at.isoformat(),
        processed_at=None,
    )


def _to_detail(plan: ImprovementPlan) -> ImprovementPlanDetail:
    summary = _to_summary(plan)
    return ImprovementPlanDetail(
        id=summary.id,
        title=summary.title,
        goal=summary.goal,
        status=summary.status,
        kind=summary.kind,
        files=summary.files,
        created_at=summary.created_at,
        processed_at=summary.processed_at,
        body=plan.body,
    )


def _suggestion_detail(note: InternalNote) -> ImprovementPlanDetail:
    summary = _suggestion_summary(note)
    return ImprovementPlanDetail(
        id=summary.id,
        title=summary.title,
        goal=summary.goal,
        status=summary.status,
        kind=summary.kind,
        files=summary.files,
        created_at=summary.created_at,
        processed_at=summary.processed_at,
        body=_suggestion_body(note),
    )


class ImprovementPlanFacade:
    def list_plans(self, *, limit: int) -> list[ImprovementPlanSummary]:
        drafted = [_to_summary(plan) for plan in improvement_plans.list_plans(limit=limit)]
        suggestions: list[ImprovementPlanSummary] = []
        if not improvement_plans.has_unprocessed_plan():
            pending = internal_notes.list_pending_self_improvement_notes(limit=1)
            if pending:
                suggestions = [_suggestion_summary(pending[0])]
        merged = drafted + suggestions
        merged.sort(key=lambda item: item.created_at, reverse=True)
        return merged[:limit]

    def get_plan(self, plan_id: int) -> ImprovementPlanDetail | None:
        plan = improvement_plans.get_plan(plan_id)
        if plan is None:
            return None
        return _to_detail(plan)

    def get_suggestion(self, note_id: int) -> ImprovementPlanDetail | None:
        note = internal_notes.get_internal_note(note_id)
        if note is None or note.kind != "self_improvement_suggestion":
            return None
        return _suggestion_detail(note)

    def process_suggestion(self, note_id: int) -> bool:
        return internal_notes.delete_self_improvement_suggestion(note_id)

    def process_plan(self, plan_id: int) -> bool:
        return improvement_plans.delete_plan(plan_id)

    def implement_plan(self, plan_id: int) -> tuple[ImplementPlanResult | None, str | None, int]:
        plan = improvement_plans.get_plan(plan_id)
        preflight = check_implementation_preflight(plan)
        if not preflight.ok:
            return None, preflight.error, preflight.status_code

        if not improvement_plans.try_mark_implementing(plan_id):
            return None, "Plan is not available for implementation.", 409

        captured_plan_id = plan_id

        def _run_implementation() -> None:
            ImprovementPlanImplementationService().run(captured_plan_id)

        run_background(
            _run_implementation,
            label=f"implement-plan-{plan_id}",
        )
        return ImplementPlanResult(ok=True, plan_id=plan_id, status="implementing"), None, 202
