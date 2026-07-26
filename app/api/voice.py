from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_voice_service
from app.voice.service import GladosVoiceService, VoiceUnavailableError
from app.voice.volume import get_voice_volume, set_voice_volume

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1)


class VoiceVolumeRequest(BaseModel):
    volume: float = Field(ge=0.0, le=1.0)


@router.get("/status")
def voice_status(voice: GladosVoiceService = Depends(get_voice_service)) -> dict[str, str | bool]:  # noqa: B008
    """Return voice service status."""
    return voice.status()


@router.get("/volume")
def voice_volume() -> dict[str, float]:
    """Return the current server-side voice playback volume."""
    return {"volume": get_voice_volume()}


@router.put("/volume")
def update_voice_volume(request: VoiceVolumeRequest) -> dict[str, float]:
    """Update server-side voice playback volume."""
    return {"volume": set_voice_volume(request.volume)}


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
