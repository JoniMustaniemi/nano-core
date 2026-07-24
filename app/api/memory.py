from fastapi import APIRouter
from pydantic import BaseModel

from app.memory import improvement_plans
from app.memory.internal_notes import list_internal_notes
from app.memory.models import ChatMessage, InternalNote
from app.memory.repository import (
    list_recent_chat_messages,
)

router = APIRouter(prefix="/api", tags=["memory"])


class ImprovementPlanStorageRecord(BaseModel):
    id: int
    title: str
    goal: str
    status: str
    created_at: str


class StorageSnapshot(BaseModel):
    chat_messages: list[ChatMessage]
    internal_notes: list[InternalNote]
    improvement_plans: list[ImprovementPlanStorageRecord]


@router.get("/storage", response_model=StorageSnapshot)
def read_storage_snapshot() -> StorageSnapshot:
    """
    Read storage snapshot.

    Returns:
        StorageSnapshot result.
    """
    return StorageSnapshot(
        chat_messages=list_recent_chat_messages(),
        internal_notes=list_internal_notes(),
        improvement_plans=[
            ImprovementPlanStorageRecord(
                id=plan.id or 0,
                title=plan.title,
                goal=plan.goal,
                status=plan.status,
                created_at=plan.created_at.isoformat(),
            )
            for plan in improvement_plans.list_plans()
            if plan.id is not None
        ],
    )
