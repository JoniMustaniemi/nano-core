import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.runtime.activity import activity

router = APIRouter(tags=["runtime"])


@router.get("/api/status")
def status() -> dict[str, object]:
    return activity.snapshot()


@router.get("/events")
async def events(request: Request, since: int = Query(default=0, ge=0)) -> StreamingResponse:
    async def stream() -> AsyncGenerator[str, None]:
        last_id = since
        while True:
            if await request.is_disconnected():
                break
            snapshot = activity.snapshot()
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
