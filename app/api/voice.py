from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.voice.service import GladosVoiceService, VoiceUnavailableError
from app.voice.volume import get_voice_volume, set_voice_volume

router = APIRouter(prefix="/api/voice", tags=["voice"])


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1)


class VoiceVolumeRequest(BaseModel):
    volume: float = Field(ge=0.0, le=1.0)


@router.get("/status")
def voice_status() -> dict[str, str | bool]:
    """
    Return voice service status for status.

    Returns:
        Dictionary containing the requested data.
    """
    return GladosVoiceService().status()


@router.get("/volume")
def voice_volume() -> dict[str, float]:
    """
    Return the current server-side voice playback volume.

    Returns:
        Current volume level between 0.0 and 1.0.
    """
    return {"volume": get_voice_volume()}


@router.put("/volume")
def update_voice_volume(request: VoiceVolumeRequest) -> dict[str, float]:
    """
    Update server-side voice playback volume.

    Args:
        request: Incoming volume update request.

    Returns:
        Updated volume level between 0.0 and 1.0.
    """
    return {"volume": set_voice_volume(request.volume)}


@router.post("")
def synthesize_voice(request: VoiceRequest) -> Response:
    """
    Synthesize voice.

    Args:
        request: Incoming API request object.

    Returns:
        Response result.

    Raises:
        HTTPException: If the operation cannot be completed.
    """
    try:
        audio = GladosVoiceService().synthesize_wav_for_client(request.text)
    except VoiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
