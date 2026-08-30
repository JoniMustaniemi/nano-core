from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.memory import repository
from app.memory.labels import InvalidTimerLabelError, normalize_timer_label
from app.memory.repository import COUNTDOWN_KIND, STOPWATCH_KIND
from app.timers.operations import remove_countdown_timer, remove_stopwatch
from app.timers.serialization import serialize_stopwatch_by_id, serialize_timer_by_id

router = APIRouter(tags=["timers"])


class LabelUpdate(BaseModel):
    label: str


@router.patch("/timers/{timer_id}")
def patch_timer(timer_id: int, body: LabelUpdate) -> dict[str, int | str]:
    """Rename one active countdown timer."""
    timer = repository.get_timer(timer_id)
    if timer is None or timer.kind != COUNTDOWN_KIND:
        raise HTTPException(status_code=404, detail="Timer not found.")
    try:
        label = normalize_timer_label(body.label, "Timer")
    except InvalidTimerLabelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    updated = repository.update_timer_label(timer_id, label)
    if updated is None:
        raise HTTPException(status_code=404, detail="Timer not found.")
    serialized = serialize_timer_by_id(timer_id)
    if serialized is None:
        raise HTTPException(status_code=404, detail="Timer not found.")
    return serialized


@router.delete("/timers/{timer_id}", status_code=204)
def delete_timer(timer_id: int) -> None:
    """Cancel one active countdown timer."""
    if not remove_countdown_timer(timer_id):
        raise HTTPException(status_code=404, detail="Timer not found.")


@router.patch("/stopwatches/{stopwatch_id}")
def patch_stopwatch(stopwatch_id: int, body: LabelUpdate) -> dict[str, int | str]:
    """Rename one active stopwatch."""
    stopwatch = repository.get_timer(stopwatch_id)
    if stopwatch is None or stopwatch.kind != STOPWATCH_KIND:
        raise HTTPException(status_code=404, detail="Stopwatch not found.")
    try:
        label = normalize_timer_label(body.label, "Stopwatch")
    except InvalidTimerLabelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    updated = repository.update_timer_label(stopwatch_id, label)
    if updated is None:
        raise HTTPException(status_code=404, detail="Stopwatch not found.")
    serialized = serialize_stopwatch_by_id(stopwatch_id)
    if serialized is None:
        raise HTTPException(status_code=404, detail="Stopwatch not found.")
    return serialized


@router.delete("/stopwatches/{stopwatch_id}", status_code=204)
def delete_stopwatch(stopwatch_id: int) -> None:
    """Stop one active stopwatch."""
    if not remove_stopwatch(stopwatch_id):
        raise HTTPException(status_code=404, detail="Stopwatch not found.")
