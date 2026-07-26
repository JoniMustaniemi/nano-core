from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.tools.improvement_plan_facade import ImprovementPlanFacade

router = APIRouter(tags=["improvement-plans"])
_facade = ImprovementPlanFacade()


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


class ImplementPlanResponse(BaseModel):
    ok: bool
    plan_id: int
    status: str


class PreflightPlanResponse(BaseModel):
    ok: bool
    error: str | None = None


@router.get("/improvement-plans", response_model=list[ImprovementPlanSummary])
def read_improvement_plans(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ImprovementPlanSummary]:
    return [
        ImprovementPlanSummary.model_validate(asdict(item))
        for item in _facade.list_plans(limit=limit)
    ]


@router.get("/improvement-plans/suggestions/{note_id}", response_model=ImprovementPlanDetail)
def read_improvement_suggestion(note_id: int) -> ImprovementPlanDetail:
    detail = _facade.get_suggestion(note_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Improvement suggestion not found.")
    return ImprovementPlanDetail.model_validate(asdict(detail))


@router.get("/improvement-plans/{plan_id}", response_model=ImprovementPlanDetail)
def read_improvement_plan(plan_id: int) -> ImprovementPlanDetail:
    detail = _facade.get_plan(plan_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Improvement plan not found.")
    return ImprovementPlanDetail.model_validate(asdict(detail))


@router.post("/improvement-plans/suggestions/{note_id}/process", status_code=204)
def process_improvement_suggestion(note_id: int) -> None:
    if not _facade.process_suggestion(note_id):
        raise HTTPException(status_code=404, detail="Improvement suggestion not found.")


@router.post("/improvement-plans/{plan_id}/process", status_code=204)
def process_improvement_plan(plan_id: int) -> None:
    if not _facade.process_plan(plan_id):
        raise HTTPException(status_code=404, detail="Improvement plan not found.")


@router.get(
    "/improvement-plans/{plan_id}/preflight",
    response_model=PreflightPlanResponse,
)
def preflight_improvement_plan(plan_id: int) -> PreflightPlanResponse:
    plan = _facade.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Improvement plan not found.")
    result = _facade.preflight_plan(plan_id)
    return PreflightPlanResponse.model_validate(asdict(result))


@router.post("/improvement-plans/{plan_id}/reset", status_code=204)
def reset_improvement_plan(plan_id: int) -> None:
    result = _facade.reset_plan(plan_id)
    if result == "not_found":
        raise HTTPException(status_code=404, detail="Improvement plan not found.")
    if result == "worker_active":
        raise HTTPException(
            status_code=409,
            detail="Implementation is still running. Try again shortly.",
        )
    if result != "ok":
        raise HTTPException(
            status_code=409,
            detail="Plan is not in implementing status.",
        )


@router.post(
    "/improvement-plans/{plan_id}/implement",
    status_code=202,
    response_model=ImplementPlanResponse,
)
def implement_improvement_plan(plan_id: int) -> ImplementPlanResponse:
    result, error, status_code = _facade.implement_plan(plan_id)
    if result is None:
        raise HTTPException(status_code=status_code, detail=error)
    return ImplementPlanResponse.model_validate(asdict(result))
