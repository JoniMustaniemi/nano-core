from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.tools.errors import ToolError
from app.voice.service import VoiceUnavailableError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ToolError)
    async def handle_tool_error(_request: Request, exc: ToolError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})

    @app.exception_handler(VoiceUnavailableError)
    async def handle_voice_unavailable(
        _request: Request, exc: VoiceUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
