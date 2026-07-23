from __future__ import annotations

DEFAULT_VOICE_VOLUME = 0.8

_VOICE_VOLUME = DEFAULT_VOICE_VOLUME


def get_voice_volume() -> float:
    """
    Return the current playback volume for server-side voice output.

    Returns:
        Volume level between 0.0 and 1.0.
    """
    return _VOICE_VOLUME


def set_voice_volume(volume: float) -> float:
    """
    Set the playback volume for server-side voice output.

    Args:
        volume: Desired volume level between 0.0 and 1.0.

    Returns:
        Clamped volume level that was stored.
    """
    global _VOICE_VOLUME
    _VOICE_VOLUME = max(0.0, min(1.0, float(volume)))
    return _VOICE_VOLUME
