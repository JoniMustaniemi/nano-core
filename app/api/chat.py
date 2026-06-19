from fastapi import APIRouter

from app.assistant.service import AssistantService
from app.llm.schemas import ChatRequest, ChatResponse

router = APIRouter()


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return AssistantService().respond(request.message)
