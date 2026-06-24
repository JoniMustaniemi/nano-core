from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.voice.service import GladosVoiceService, VoiceUnavailableError

router = APIRouter(prefix="/api/voice", tags=["voice"])


class VoiceRequest(BaseModel):
    text: str = Field(min_length=1)


@router.get("/status")
def voice_status() -> dict[str, str | bool]:
    """
    Return voice service status for status.

    Returns:
        Dictionary containing the requested data.
    """
    return GladosVoiceService().status()


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
        audio = GladosVoiceService().synthesize_wav(request.text)
    except VoiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
