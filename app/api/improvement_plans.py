from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.memory import improvement_plans
from app.memory.models import ImprovementPlan

router = APIRouter(prefix="/api", tags=["improvement-plans"])


class ImprovementPlanSummary(BaseModel):
    id: int
    title: str
    goal: str
    status: str
    files: list[str]
    created_at: str
    processed_at: str | None = None


class ImprovementPlanDetail(ImprovementPlanSummary):
    body: str


def _to_summary(plan: ImprovementPlan) -> ImprovementPlanSummary:
    if plan.id is None:
        raise ValueError("Plan must have an id")
    try:
        files = json.loads(plan.files_json)
        if not isinstance(files, list):
            files = []
    except json.JSONDecodeError:
        files = []
    return ImprovementPlanSummary(
        id=plan.id,
        title=plan.title,
        goal=plan.goal,
        status=plan.status,
        files=[str(path) for path in files],
        created_at=plan.created_at.isoformat(),
        processed_at=plan.processed_at.isoformat() if plan.processed_at else None,
    )


def _to_detail(plan: ImprovementPlan) -> ImprovementPlanDetail:
    summary = _to_summary(plan)
    return ImprovementPlanDetail(**summary.model_dump(), body=plan.body)


@router.get("/improvement-plans", response_model=list[ImprovementPlanSummary])
def read_improvement_plans(limit: int = Query(default=20, ge=1, le=100)) -> list[ImprovementPlanSummary]:
    return [_to_summary(plan) for plan in improvement_plans.list_plans(limit=limit)]


@router.get("/improvement-plans/{plan_id}", response_model=ImprovementPlanDetail)
def read_improvement_plan(plan_id: int) -> ImprovementPlanDetail:
    plan = improvement_plans.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Improvement plan not found.")
    return _to_detail(plan)


@router.post("/improvement-plans/{plan_id}/process", response_model=ImprovementPlanDetail)
def process_improvement_plan(plan_id: int) -> ImprovementPlanDetail:
    plan = improvement_plans.mark_processed(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Improvement plan not found.")
    return _to_detail(plan)
