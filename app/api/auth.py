from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import get_settings

_API_PREFIX = "/api"
_HEALTH_PATH = "/api/health"


def _extract_api_key(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    query_key = request.query_params.get("api_key")
    if query_key:
        return query_key.strip()
    return None


def _is_public_api_path(path: str) -> bool:
    return path == _HEALTH_PATH or path == f"{_HEALTH_PATH}/"


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Require a shared API key for /api routes except health checks."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if not path.startswith(_API_PREFIX) or _is_public_api_path(path):
            return await call_next(request)

        settings = get_settings()
        configured_key = settings.api_key.strip()
        if not configured_key:
            if settings.app_env == "development":
                return await call_next(request)
            return JSONResponse(
                status_code=503,
                content={"detail": "API key is not configured on the server."},
            )

        provided_key = _extract_api_key(request)
        if provided_key != configured_key:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key."})

        return await call_next(request)
