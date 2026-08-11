from __future__ import annotations

import io
import wave
from typing import Protocol


class SpeechToTextError(RuntimeError):
    """Raised when speech-to-text is unavailable or fails."""


class SpeechToTextBackend(Protocol):
    def transcribe_wav(self, wav_bytes: bytes) -> str: ...


class VoskSpeechToText:
    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._model = None

    def _get_model(self) -> object:
        if self._model is not None:
            return self._model
        try:
            from vosk import Model, SetLogLevel
        except ImportError as exc:
            raise SpeechToTextError(
                "Vosk is not installed. Install the voice extra: pip install nano-core[voice]."
            ) from exc

        SetLogLevel(-1)
        try:
            self._model = Model(self._model_path)
        except Exception as exc:
            raise SpeechToTextError(f"Could not load Vosk model at {self._model_path}: {exc}") from exc
        return self._model

    def transcribe_wav(self, wav_bytes: bytes) -> str:
        try:
            from vosk import KaldiRecognizer
        except ImportError as exc:
            raise SpeechToTextError("Vosk is not installed.") from exc

        sample_rate = _wav_sample_rate(wav_bytes)
        pcm_bytes = _wav_pcm_bytes(wav_bytes)
        recognizer = KaldiRecognizer(self._get_model(), sample_rate)
        recognizer.SetWords(False)
        recognizer.AcceptWaveform(pcm_bytes)
        import json

        result = json.loads(recognizer.FinalResult())
        transcript = str(result.get("text", "")).strip()
        if not transcript:
            raise SpeechToTextError("No speech detected in audio.")
        return transcript


def _wav_sample_rate(wav_bytes: bytes) -> int:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        return wav_file.getframerate()


def _wav_pcm_bytes(wav_bytes: bytes) -> bytes:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        return wav_file.readframes(wav_file.getnframes())


def get_stt_backend() -> SpeechToTextBackend:
    from app.config import get_settings

    settings = get_settings()
    if settings.stt_backend == "vosk":
        return VoskSpeechToText(settings.stt_model_path)
    raise SpeechToTextError(f"Unsupported STT backend: {settings.stt_backend}")


def transcribe_audio(wav_bytes: bytes) -> str:
    """
    Transcribe WAV audio bytes to text.

    Args:
        wav_bytes: WAV-encoded audio.

    Returns:
        Transcript text.
    """
    return get_stt_backend().transcribe_wav(wav_bytes)
