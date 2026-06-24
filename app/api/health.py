from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.health import HealthCheckResult, run_health_checks

router = APIRouter(tags=["health"])


class HealthPayload(BaseModel):
    status: str
    app: str
    environment: str
    checks: list[HealthCheckResult]


@router.get("/health")
def health() -> HealthPayload:
    """
    Return service health information.

    Returns:
        HealthPayload result.
    """
    settings = get_settings()
    checks = run_health_checks()
    overall = "ok" if all(check.ok for check in checks) else "error"
    return HealthPayload(
        status=overall,
        app=settings.app_name,
        environment=settings.app_env,
        checks=checks,
    )
