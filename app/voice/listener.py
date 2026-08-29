from __future__ import annotations

import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from app.assistant.service import AssistantService
from app.config import get_settings
from app.runtime.activity import activity
from app.voice.service import GladosVoiceService, VoiceUnavailableError
from app.voice.stt import SpeechToTextError, transcribe_audio

_listener_thread: threading.Thread | None = None
_stop_event = threading.Event()
_listening = False


def is_local_listener_running() -> bool:
    return _listening and _listener_thread is not None and _listener_thread.is_alive()


def start_voice_listener() -> None:
    global _listener_thread

    settings = get_settings()
    if not settings.voice_input_enabled:
        return
    if _listener_thread is not None and _listener_thread.is_alive():
        return

    _stop_event.clear()
    _listener_thread = threading.Thread(
        target=_listener_loop, name="nano-voice-listener", daemon=True
    )
    _listener_thread.start()


def stop_voice_listener() -> None:
    _stop_event.set()
    if _listener_thread is not None and _listener_thread.is_alive():
        _listener_thread.join(timeout=2.0)


def _listener_loop() -> None:
    global _listening

    _listening = True
    try:
        while not _stop_event.is_set():
            try:
                audio = _record_audio(duration_seconds=3.0)
                transcript = transcribe_audio(audio).lower()
            except SpeechToTextError:
                continue
            except Exception:
                time.sleep(0.5)
                continue

            if not _contains_wake_phrase(transcript):
                continue

            command = _extract_command(transcript)
            _handle_wake()
            if not command:
                try:
                    command_audio = _record_audio(
                        duration_seconds=get_settings().voice_command_timeout_seconds
                    )
                    command = transcribe_audio(command_audio)
                except SpeechToTextError:
                    continue

            if command.strip():
                _handle_command(command.strip())
    finally:
        _listening = False


def _contains_wake_phrase(transcript: str) -> bool:
    wake_phrase = get_settings().voice_wake_phrase.strip().lower()
    return wake_phrase in transcript


def _extract_command(transcript: str) -> str:
    wake_phrase = get_settings().voice_wake_phrase.strip().lower()
    pattern = re.compile(rf"{re.escape(wake_phrase)}\s*,?\s*(.*)$", re.IGNORECASE)
    match = pattern.search(transcript)
    if match is None:
        return ""
    return match.group(1).strip()


def _handle_wake() -> None:
    response = AssistantService().wake_response()
    activity.log(title=response.content, detail=response.content, source="assistant.wake")
    try:
        GladosVoiceService().announce(response.content)
    except VoiceUnavailableError:
        pass


def _handle_command(message: str) -> None:
    response = AssistantService().respond(message, mode="agent")
    activity.log(title=response.content, detail=response.content, source="assistant.chat")
    if response.speak:
        try:
            GladosVoiceService().announce(response.content)
        except VoiceUnavailableError:
            pass


def _record_audio(duration_seconds: float) -> bytes:
    settings = get_settings()
    device_args: list[str] = []
    if settings.voice_input_device:
        device_args = ["-D", settings.voice_input_device]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as handle:
        temp_path = handle.name

    command = [
        "arecord",
        *device_args,
        "-q",
        "-f",
        "S16_LE",
        "-r",
        "16000",
        "-c",
        "1",
        "-d",
        str(max(1, int(duration_seconds))),
        temp_path,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
        return Path(temp_path).read_bytes()
    except FileNotFoundError as exc:
        raise SpeechToTextError("arecord is not available for microphone capture.") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore").strip()
        raise SpeechToTextError(stderr or "Microphone capture failed.") from exc
    finally:
        Path(temp_path).unlink(missing_ok=True)
