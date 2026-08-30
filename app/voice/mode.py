from __future__ import annotations

from app.config import get_settings

_VOICE_MODE_ENABLED: bool = False


def init_voice_mode_from_settings() -> None:
    """Boot-time init: honor VOICE_INPUT_ENABLED env default."""
    global _VOICE_MODE_ENABLED
    _VOICE_MODE_ENABLED = get_settings().voice_input_enabled


def get_voice_mode_enabled() -> bool:
    """Return whether Pi-side wake-word listening is enabled."""
    return _VOICE_MODE_ENABLED


def set_voice_mode_enabled(enabled: bool) -> bool:
    """Set whether Pi-side wake-word listening should be enabled."""
    global _VOICE_MODE_ENABLED
    _VOICE_MODE_ENABLED = bool(enabled)
    return _VOICE_MODE_ENABLED
