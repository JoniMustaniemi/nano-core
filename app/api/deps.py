from __future__ import annotations

from functools import lru_cache

from app.assistant.service import AssistantService
from app.voice.output import get_voice_output
from app.voice.protocol import VoiceOutput


@lru_cache
def get_assistant_service() -> AssistantService:
    return AssistantService()


@lru_cache
def get_voice_service() -> VoiceOutput:
    return get_voice_output()
