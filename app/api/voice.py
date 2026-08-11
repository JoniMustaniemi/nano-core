from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_assistant_service, get_voice_service
from app.assistant.service import AssistantService
from app.voice.listener import is_local_listener_running
from app.voice.service import GladosVoiceService, VoiceUnavailableError
from app.voice.audio_convert import normalize_audio_to_wav
from app.voice.stt import SpeechToTextError, transcribe_audio
from app.voice.volume import get_voice_volume, set_voice_volume

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1)


class VoiceVolumeRequest(BaseModel):
    volume: float = Field(ge=0.0, le=1.0)


class TranscriptResponse(BaseModel):
    transcript: str


@router.get("/status")
def voice_status(voice: GladosVoiceService = Depends(get_voice_service)) -> dict[str, str | bool]:  # noqa: B008
    """Return voice service status."""
    status = voice.status()
    from app.config import get_settings

    settings = get_settings()
    status["input_enabled"] = settings.voice_input_enabled
    status["input_device"] = settings.voice_input_device
    status["output_device"] = settings.voice_output_device
    status["stt_backend"] = settings.stt_backend
    status["listening"] = is_local_listener_running()
    status["playback_mode"] = settings.voice_playback_mode
    return status


@router.get("/volume")
def voice_volume() -> dict[str, float]:
    """Return the current server-side voice playback volume."""
    return {"volume": get_voice_volume()}


@router.put("/volume")
def update_voice_volume(request: VoiceVolumeRequest) -> dict[str, float]:
    """Update server-side voice playback volume."""
    return {"volume": set_voice_volume(request.volume)}


@router.post("/transcribe", response_model=TranscriptResponse)
async def transcribe_voice(audio: UploadFile = File(...)) -> TranscriptResponse:
    """Transcribe uploaded audio on the Pi."""
    payload = await audio.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Audio payload is empty.")
    try:
        wav_bytes = normalize_audio_to_wav(payload, content_type=audio.content_type or "")
        transcript = transcribe_audio(wav_bytes)
    except SpeechToTextError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return TranscriptResponse(transcript=transcript)


@router.post("/command")
async def voice_command(
    audio: UploadFile = File(...),
    assistant: AssistantService = Depends(get_assistant_service),  # noqa: B008
) -> dict[str, object]:
    """Transcribe uploaded audio and process it as an agent command."""
    payload = await audio.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Audio payload is empty.")
    try:
        wav_bytes = normalize_audio_to_wav(payload, content_type=audio.content_type or "")
        transcript = transcribe_audio(wav_bytes)
    except SpeechToTextError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    response = assistant.respond(transcript, mode="agent")
    return {
        "transcript": transcript,
        "content": response.content,
        "speak": response.speak,
        "mode": response.mode,
    }


@router.post("")
def synthesize_voice(
    request: VoiceRequest,
    voice: GladosVoiceService = Depends(get_voice_service),  # noqa: B008
) -> Response:
    """Synthesize voice audio for the given text."""
    try:
        audio = voice.synthesize_wav_for_client(request.text)
    except VoiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
