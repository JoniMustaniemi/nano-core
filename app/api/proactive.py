from fastapi import APIRouter

from app.proactive.store import proactive_store

router = APIRouter(tags=["proactive"])


@router.get("/api/proactive")
def proactive_status() -> dict[str, object]:
  """Return current proactive outreach state for the web UI."""
  return proactive_store.snapshot()
