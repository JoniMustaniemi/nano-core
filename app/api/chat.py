from fastapi import APIRouter, Depends

from app.api.deps import get_assistant_service
from app.assistant.service import AssistantService
from app.llm.schemas import ChatRequest, ChatResponse
from app.runtime.activity import activity

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    assistant: AssistantService = Depends(get_assistant_service),  # noqa: B008
) -> ChatResponse:
    """Handle chat input and return a response."""
    try:
        return assistant.respond(request.message, mode=request.mode)
    except Exception:
        activity.release_to_idle(source="api.chat")
        return ChatResponse(
            content="Something went wrong while I was working on that. Please try again.",
            speak=False,
        )


@router.get("/chat/wake", response_model=ChatResponse)
def wake(assistant: AssistantService = Depends(get_assistant_service)) -> ChatResponse:  # noqa: B008
    """Return the wake acknowledgement."""
    return assistant.wake_response()
