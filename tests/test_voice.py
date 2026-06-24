from fastapi.testclient import TestClient

from app.main import app
from app.voice.service import GladosVoiceService


def test_voice_status_reports_backend(monkeypatch) -> None:
    """
    Verify that voice status reports backend.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    monkeypatch.setattr(
        "app.api.voice.GladosVoiceService.status",
        lambda self: {
            "available": True,
            "backend": "glados",
            "detail": "GLaDOS voice is ready.",
        },
    )

    with TestClient(app) as client:
        response = client.get("/api/voice/status")

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["backend"] == "glados"


def test_voice_endpoint_returns_wav(monkeypatch) -> None:
    """
    Verify that voice endpoint returns wav.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    monkeypatch.setattr(
        "app.api.voice.GladosVoiceService.synthesize_wav",
        lambda self, text: b"RIFFdemoWAVE",
    )

    with TestClient(app) as client:
        response = client.post("/api/voice", json={"text": "hello"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFFdemoWAVE"


def test_voice_service_announce_synthesizes_and_plays(monkeypatch) -> None:
    """
    Verify that voice service announce synthesizes and plays.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    played: list[bytes] = []
    monkeypatch.setattr(
        "app.voice.service.GladosVoiceService.synthesize_wav",
        lambda self, text: b"RIFFdemoWAVE",
    )
    monkeypatch.setattr(
        "app.voice.service._play_wav_bytes",
        lambda wav_bytes: played.append(wav_bytes),
    )

    GladosVoiceService().announce("timer complete")

    assert played == [b"RIFFdemoWAVE"]
