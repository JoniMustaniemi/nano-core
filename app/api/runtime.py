import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.runtime.activity import activity
from app.runtime.status_copy import choose_standby_greeting

router = APIRouter(tags=["runtime"])


@router.get("/api/greeting")
def greeting() -> dict[str, str]:
    """Return a short idle greeting for the home UI."""
    return {"greeting": choose_standby_greeting()}


@router.get("/api/status")
def status() -> dict[str, object]:
    """
    Return status information for the requested operation.

    Returns:
        Dictionary containing the requested data.
    """
    return activity.snapshot()


@router.get("/events")
async def events(request: Request, since: int = Query(default=0, ge=0)) -> StreamingResponse:
    """
    Stream runtime activity events.

    Args:
        request: Incoming API request object.
        since: Last seen runtime activity event identifier.

    Returns:
        StreamingResponse result.
    """

    async def stream() -> AsyncGenerator[str, None]:
        """
        Yield serialized runtime activity events.

        Returns:
            Parsed value when available; otherwise None.
        """
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
