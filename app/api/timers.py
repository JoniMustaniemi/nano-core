from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.memory import repository
from app.memory.labels import InvalidTimerLabelError, normalize_timer_label
from app.memory.repository import COUNTDOWN_KIND, STOPWATCH_KIND
from app.timers.operations import (
    create_countdown_timer,
    create_stopwatch,
    remove_countdown_timer,
    remove_stopwatch,
)
from app.timers.serialization import serialize_stopwatch_by_id, serialize_timer_by_id
from app.tools.errors import ToolError

router = APIRouter(tags=["timers"])

# UI sends client commit time (epoch ms); allow clock skew and request latency.
_START_AT_PAST_GRACE = timedelta(seconds=30)


class LabelUpdate(BaseModel):
    label: str


def _coerce_start_at(value: Any) -> Any:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if abs(timestamp) > 1e11:
            timestamp /= 1000.0
        return datetime.fromtimestamp(timestamp, tz=UTC)
    return value


def _normalize_request_start_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        started_at = value.replace(tzinfo=UTC)
    else:
        started_at = value.astimezone(UTC)
    now = datetime.now(UTC)
    if started_at < now - _START_AT_PAST_GRACE:
        raise HTTPException(status_code=400, detail="start_at cannot be in the past.")
    return started_at


class TimerCreate(BaseModel):
    duration_seconds: int = Field(gt=0)
    label: str = "Timer"
    start_at: datetime | None = None

    @field_validator("start_at", mode="before")
    @classmethod
    def coerce_timer_start_at(cls, value: Any) -> Any:
        return _coerce_start_at(value)


class StopwatchCreate(BaseModel):
    label: str = "Stopwatch"
    start_at: datetime | None = None

    @field_validator("start_at", mode="before")
    @classmethod
    def coerce_stopwatch_start_at(cls, value: Any) -> Any:
        return _coerce_start_at(value)


@router.post("/timers", status_code=201)
def post_timer(body: TimerCreate) -> dict[str, int | str]:
    """Create a countdown timer with an exact duration."""
    try:
        label = normalize_timer_label(body.label, "Timer")
    except InvalidTimerLabelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    started_at = _normalize_request_start_at(body.start_at)

    try:
        timer = create_countdown_timer(
            duration_seconds=body.duration_seconds,
            label=label,
            started_at=started_at,
        )
    except ToolError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if timer.id is None:
        raise HTTPException(status_code=500, detail="Timer could not be created.")
    serialized = serialize_timer_by_id(timer.id)
    if serialized is None:
        raise HTTPException(status_code=500, detail="Timer could not be serialized.")
    return serialized


@router.post("/stopwatches", status_code=201)
def post_stopwatch(body: StopwatchCreate) -> dict[str, int | str]:
    """Start a stopwatch."""
    try:
        label = normalize_timer_label(body.label, "Stopwatch")
    except InvalidTimerLabelError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    started_at = _normalize_request_start_at(body.start_at)

    stopwatch = create_stopwatch(label=label, started_at=started_at)
    if stopwatch.id is None:
        raise HTTPException(status_code=500, detail="Stopwatch could not be created.")
    serialized = serialize_stopwatch_by_id(stopwatch.id)
    if serialized is None:
        raise HTTPException(status_code=500, detail="Stopwatch could not be serialized.")
    return serialized


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
