from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from app.voice.stt import SpeechToTextError


def normalize_audio_to_wav(audio_bytes: bytes, *, content_type: str = "") -> bytes:
    """
    Convert uploaded audio into mono 16 kHz WAV for STT.

    Args:
        audio_bytes: Raw uploaded audio bytes.
        content_type: Optional MIME type hint.

    Returns:
        WAV bytes suitable for Vosk transcription.
    """
    if not audio_bytes:
        raise SpeechToTextError("Audio payload is empty.")

    if _looks_like_wav(audio_bytes):
        return audio_bytes

    if content_type.startswith("audio/wav") or content_type.startswith("audio/x-wav"):
        return audio_bytes

    converted = _convert_with_ffmpeg(audio_bytes)
    if converted is not None:
        return converted

    raise SpeechToTextError(
        "Unsupported audio format. Install ffmpeg on the Pi or upload WAV audio."
    )


def _looks_like_wav(audio_bytes: bytes) -> bool:
    return len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"


def _convert_with_ffmpeg(audio_bytes: bytes) -> bytes | None:
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        return None

    input_path: str | None = None
    output_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".input") as input_file:
            input_file.write(audio_bytes)
            input_path = input_file.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as output_file:
            output_path = output_file.name

        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                input_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                output_path,
            ],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="ignore").strip()
            raise SpeechToTextError(stderr or "Audio conversion failed.")
        return Path(output_path).read_bytes()
    except FileNotFoundError as exc:
        raise SpeechToTextError("ffmpeg is not available for audio conversion.") from exc
    finally:
        if input_path is not None:
            Path(input_path).unlink(missing_ok=True)
        if output_path is not None:
            Path(output_path).unlink(missing_ok=True)


def _find_ffmpeg() -> str | None:
    from shutil import which

    return which("ffmpeg")
