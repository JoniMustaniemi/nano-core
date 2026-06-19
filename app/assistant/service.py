from app.assistant.prompts import SYSTEM_PROMPT
from app.assistant.router import get_llm_client
from app.llm.schemas import ChatResponse


class AssistantService:
    def respond(self, message: str) -> ChatResponse:
        client = get_llm_client()
        content = client.complete(system_prompt=SYSTEM_PROMPT, user_message=message)
        return ChatResponse(content=content)
