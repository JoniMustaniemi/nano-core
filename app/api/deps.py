from __future__ import annotations

from functools import lru_cache

from app.assistant.service import AssistantService
from app.voice.service import GladosVoiceService


@lru_cache
def get_assistant_service() -> AssistantService:
    return AssistantService()


@lru_cache
def get_voice_service() -> GladosVoiceService:
    return GladosVoiceService()
