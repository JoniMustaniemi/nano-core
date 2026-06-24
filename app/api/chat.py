from fastapi import APIRouter

from app.assistant.service import AssistantService
from app.llm.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    Handle chat input and return a response.

    Args:
        request: Incoming API request object.

    Returns:
        ChatResponse result.
    """
    return AssistantService().respond(request.message, mode=request.mode)


@router.get("/wake", response_model=ChatResponse)
def wake() -> ChatResponse:
    """
    Return the wake response for the requested operation.

    Returns:
        ChatResponse result.
    """
    return AssistantService().wake_response()
