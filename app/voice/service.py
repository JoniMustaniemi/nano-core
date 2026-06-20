from __future__ import annotations

import importlib
import io
import sys
import wave
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings


class VoiceUnavailableError(RuntimeError):
    """Raised when the configured voice backend is not ready."""


class GladosVoiceService:
    def status(self) -> dict[str, str | bool]:
        try:
            _get_glados_tts()
        except VoiceUnavailableError as exc:
            return {
                "available": False,
                "backend": "glados",
                "detail": str(exc),
            }

        return {
            "available": True,
            "backend": "glados",
            "detail": "GLaDOS voice is ready.",
        }

    def synthesize_wav(self, text: str) -> bytes:
        try:
            tts = _get_glados_tts()
            audio = tts.generate_speech_audio(text)
        except VoiceUnavailableError:
            raise
        except Exception as exc:  # pragma: no cover - depends on optional runtime
            raise VoiceUnavailableError(
                f"GLaDOS voice synthesis failed: {exc}"
            ) from exc

        settings = get_settings()
        sample_rate = int(getattr(tts, "sample_rate", settings.voice_sample_rate))
        return _audio_to_wav_bytes(audio, sample_rate)


@lru_cache(maxsize=1)
def _get_glados_tts() -> Any:
    module = _load_glados_module()
    try:
        return module.TTS()
    except AttributeError as exc:
        raise VoiceUnavailableError(
            "GLaDOS-TTS was found, but the TTS class is missing."
        ) from exc
    except Exception as exc:  # pragma: no cover - depends on optional runtime
        raise VoiceUnavailableError(f"Could not initialize GLaDOS-TTS: {exc}") from exc


def _load_glados_module() -> Any:
    try:
        return importlib.import_module("glados")
    except ImportError:
        settings = get_settings()
        repo_path = Path(settings.voice_glados_repo_path).resolve()
        if not repo_path.exists():
            raise VoiceUnavailableError(
                "GLaDOS-TTS is not installed. Clone the repo into "
                f"{settings.voice_glados_repo_path} or make `glados` importable."
            ) from None

        repo_str = str(repo_path)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)

        try:
            return importlib.import_module("glados")
        except ImportError as exc:
            raise VoiceUnavailableError(
                "Found the GLaDOS-TTS repository, but Python still could not import `glados`."
            ) from exc


def _audio_to_wav_bytes(audio: Any, sample_rate: int) -> bytes:
    samples = _coerce_samples(audio)
    pcm_frames = bytearray()

    for sample in samples:
        clipped = max(-1.0, min(1.0, float(sample)))
        pcm_value = int(clipped * 32767)
        pcm_frames.extend(pcm_value.to_bytes(2, byteorder="little", signed=True))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm_frames))

    return buffer.getvalue()


def _coerce_samples(audio: Any) -> list[float]:
    if hasattr(audio, "tolist"):
        data = audio.tolist()
    else:
        data = list(audio)

    if data and isinstance(data[0], list):
        flattened: list[float] = []
        for row in data:
            flattened.extend(float(item) for item in row)
        return flattened

    return [float(item) for item in data]
