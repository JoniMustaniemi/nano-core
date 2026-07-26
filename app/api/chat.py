import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import get_assistant_service
from app.assistant.service import AssistantService
from app.llm.schemas import ChatRequest, ChatResponse
from app.runtime.activity import activity

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

_CHAT_ERROR_MESSAGE = "Something went wrong while I was working on that. Please try again."


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    assistant: AssistantService = Depends(get_assistant_service),  # noqa: B008
) -> ChatResponse | JSONResponse:
    """Handle chat input and return a response."""
    try:
        return assistant.respond(request.message, mode=request.mode)
    except Exception:
        logger.exception("Chat request failed for mode=%s", request.mode)
        activity.release_to_idle(source="api.chat")
        return JSONResponse(
            status_code=500,
            content={
                "content": _CHAT_ERROR_MESSAGE,
                "speak": False,
            },
        )


@router.get("/chat/wake", response_model=ChatResponse)
def wake(assistant: AssistantService = Depends(get_assistant_service)) -> ChatResponse:  # noqa: B008
    """Return the wake acknowledgement."""
    return assistant.wake_response()
