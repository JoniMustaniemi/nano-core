import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.runtime.snapshot import build_runtime_snapshot
from app.runtime.status_copy import choose_standby_greeting

router = APIRouter(tags=["runtime"])


@router.get("/greeting")
def greeting() -> dict[str, str]:
    """Return a short idle greeting for the home UI."""
    return {"greeting": choose_standby_greeting()}


@router.get("/status")
def status() -> dict[str, object]:
    """Return the full runtime snapshot for the web UI."""
    return build_runtime_snapshot()


@router.get("/events")
async def events(request: Request, since: int = Query(default=0, ge=0)) -> StreamingResponse:
    """Stream runtime activity events."""

    async def stream() -> AsyncGenerator[str, None]:
        last_id = since
        while True:
            if await request.is_disconnected():
                break
            snapshot = build_runtime_snapshot()
            events = snapshot["events"]
            if isinstance(events, list):
                for event in events:
                    if isinstance(event, dict):
                        event_id = event.get("id")
                        if isinstance(event_id, int) and event_id > last_id:
                            last_id = event_id
                            yield f"event: activity\ndata: {json.dumps(event)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")
