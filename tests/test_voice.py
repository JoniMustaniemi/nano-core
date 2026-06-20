from fastapi.testclient import TestClient

from app.main import app


def test_voice_status_reports_backend(monkeypatch) -> None:
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
    monkeypatch.setattr(
        "app.api.voice.GladosVoiceService.synthesize_wav",
        lambda self, text: b"RIFFdemoWAVE",
    )

    with TestClient(app) as client:
        response = client.post("/api/voice", json={"text": "hello"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFFdemoWAVE"
