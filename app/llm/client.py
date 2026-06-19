import httpx

from app.config import get_settings


class LocalLLMClient:
    def complete(self, system_prompt: str, user_message: str) -> str:
        settings = get_settings()
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
        }

        try:
            response = httpx.post(
                f"{settings.llm_base_url}/api/chat",
                json=payload,
                timeout=settings.llm_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return "Local LLM is not available yet. Start hailo-ollama or configure llama.cpp."

        data = response.json()
        message = data.get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        return "Local LLM returned an empty response."
