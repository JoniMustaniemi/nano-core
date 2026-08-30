from __future__ import annotations

from functools import lru_cache

from app.voice.protocol import VoiceOutput


@lru_cache(maxsize=1)
def get_voice_output() -> VoiceOutput:
    from app.voice.service import GladosVoiceService

    return GladosVoiceService()
