from fastapi import APIRouter

from app.system.specs import serialize_system_metrics

router = APIRouter(tags=["system"])


@router.get("/system/metrics")
def system_metrics() -> dict[str, float | bool | None]:
    """Return lightweight host metrics for the web UI."""
    return serialize_system_metrics()
