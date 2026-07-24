from fastapi import APIRouter
from pydantic import BaseModel

from app.memory.internal_notes import list_internal_notes
from app.memory.models import ChatMessage, InternalNote
from app.memory.repository import (
    list_recent_chat_messages,
)

router = APIRouter(prefix="/api", tags=["memory"])


class StorageSnapshot(BaseModel):
    chat_messages: list[ChatMessage]
    internal_notes: list[InternalNote]


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
    )
