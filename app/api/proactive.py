from fastapi import APIRouter

from app.proactive.store import proactive_store
from app.runtime.activity import activity
from app.runtime.status_copy import choose_standby_greeting

router = APIRouter(tags=["proactive"])


@router.get("/api/proactive")
def proactive_status() -> dict[str, object]:
    """Return current proactive outreach state for the web UI."""
    return proactive_store.snapshot()


@router.post("/api/proactive/dismiss")
def dismiss_proactive() -> dict[str, object]:
    """Clear a consumed presence dismissal and restore default standby copy."""
    proactive_store.clear_dismissal()
    activity.standby(
        title=choose_standby_greeting(),
        detail=None,
        source="proactive.presence_gate",
    )
    return {"ok": True}
