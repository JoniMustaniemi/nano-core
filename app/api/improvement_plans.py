from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.memory import improvement_plans, internal_notes
from app.memory.models import ImprovementPlan, InternalNote
from app.proactive.types import ProactiveOffer

router = APIRouter(prefix="/api", tags=["improvement-plans"])


class ImprovementPlanSummary(BaseModel):
    id: int
    title: str
    goal: str
    status: str
    kind: str = "drafted"
    files: list[str]
    created_at: str
    processed_at: str | None = None


class ImprovementPlanDetail(ImprovementPlanSummary):
    body: str


def _parse_files(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    files: list[str] = []
    for path in raw:
        cleaned = str(path).strip()
        if cleaned and cleaned not in files:
            files.append(cleaned)
    return files


def _files_from_plan(plan: ImprovementPlan) -> list[str]:
    try:
        files = json.loads(plan.files_json)
        if not isinstance(files, list):
            return []
    except json.JSONDecodeError:
        return []
    return [str(path) for path in files]


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
    return _parse_files(offer.payload.get("files", []))


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
        files=_files_from_plan(plan),
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
        status="queued",
        kind="suggestion",
        files=_files_from_note(note),
        created_at=note.created_at.isoformat(),
        processed_at=None,
    )


def _to_detail(plan: ImprovementPlan) -> ImprovementPlanDetail:
    summary = _to_summary(plan)
    return ImprovementPlanDetail(**summary.model_dump(), body=plan.body)


def _suggestion_detail(note: InternalNote) -> ImprovementPlanDetail:
    summary = _suggestion_summary(note)
    return ImprovementPlanDetail(**summary.model_dump(), body=_suggestion_body(note))


def _merged_plans(*, limit: int) -> list[ImprovementPlanSummary]:
    drafted = [_to_summary(plan) for plan in improvement_plans.list_plans(limit=limit)]
    suggestions = [
        _suggestion_summary(note)
        for note in internal_notes.list_pending_self_improvement_notes(limit=limit)
    ]
    merged = drafted + suggestions
    merged.sort(key=lambda item: item.created_at, reverse=True)
    return merged[:limit]


@router.get("/improvement-plans", response_model=list[ImprovementPlanSummary])
def read_improvement_plans(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ImprovementPlanSummary]:
    return _merged_plans(limit=limit)


@router.get("/improvement-plans/suggestions/{note_id}", response_model=ImprovementPlanDetail)
def read_improvement_suggestion(note_id: int) -> ImprovementPlanDetail:
    note = internal_notes.get_internal_note(note_id)
    if note is None or note.kind != "self_improvement_suggestion":
        raise HTTPException(status_code=404, detail="Improvement suggestion not found.")
    return _suggestion_detail(note)


@router.get("/improvement-plans/{plan_id}", response_model=ImprovementPlanDetail)
def read_improvement_plan(plan_id: int) -> ImprovementPlanDetail:
    plan = improvement_plans.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Improvement plan not found.")
    return _to_detail(plan)


@router.post("/improvement-plans/{plan_id}/process", status_code=204)
def process_improvement_plan(plan_id: int) -> None:
    if not improvement_plans.delete_plan(plan_id):
        raise HTTPException(status_code=404, detail="Improvement plan not found.")
