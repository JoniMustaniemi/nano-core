from types import SimpleNamespace

from app.voice.service import GladosVoiceService


def _patch_voice_service(monkeypatch, **methods) -> SimpleNamespace:
    from app.api.deps import get_voice_service
    from app.voice.output import get_voice_output

    get_voice_service.cache_clear()
    get_voice_output.cache_clear()
    voice = SimpleNamespace(**methods)
    monkeypatch.setattr("app.api.deps.get_voice_service", lambda: voice)
    monkeypatch.setattr("app.api.deps.get_voice_output", lambda: voice)
    return voice


def test_voice_status_reports_backend(api_client, monkeypatch) -> None:
    """
    Verify that voice status reports backend.

    Args:
        api_client: Shared FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    _patch_voice_service(
        monkeypatch,
        status=lambda: {
            "available": True,
            "backend": "glados",
            "detail": "GLaDOS voice is ready.",
        },
    )

    response = api_client.get("/api/voice/status")

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["backend"] == "glados"


def test_voice_endpoint_returns_wav(api_client, monkeypatch) -> None:
    """
    Verify that voice endpoint returns wav.

    Args:
        api_client: Shared FastAPI test client.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        None.
    """
    _patch_voice_service(
        monkeypatch,
        synthesize_wav_for_client=lambda text: b"RIFFdemoWAVE",
    )

    response = api_client.post("/api/voice", json={"text": "hello"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFFdemoWAVE"


def test_voice_volume_endpoint_updates_server_volume(api_client) -> None:
    """
    Verify that voice volume endpoint updates server playback volume.

    Returns:
        None.
    """
    from app.voice.volume import set_voice_volume

    set_voice_volume(0.8)
    response = api_client.put("/api/voice/volume", json={"volume": 0.35})

    assert response.status_code == 200
    assert response.json()["volume"] == 0.35

    current = api_client.get("/api/voice/volume")

    assert current.status_code == 200
    assert current.json()["volume"] == 0.35

    set_voice_volume(0.8)


def test_voice_mode_put_enables_listener(api_client, monkeypatch) -> None:
    """
    Verify that PUT /api/voice/mode enables Pi-side wake-word listening.

    Returns:
        None.
    """
    from app.voice.mode import set_voice_mode_enabled

    set_voice_mode_enabled(False)
    started: list[bool] = []
    monkeypatch.setattr(
        "app.api.voice.start_voice_listener",
        lambda: started.append(True),
    )

    response = api_client.put("/api/voice/mode", json={"enabled": True})

    assert response.status_code == 200
    assert response.json() == {"enabled": True}
    assert started == [True]

    set_voice_mode_enabled(False)


def test_voice_mode_put_disables_listener(api_client, monkeypatch) -> None:
    """
    Verify that PUT /api/voice/mode disables Pi-side wake-word listening.

    Returns:
        None.
    """
    from app.voice.mode import set_voice_mode_enabled

    set_voice_mode_enabled(True)
    stopped: list[bool] = []
    monkeypatch.setattr(
        "app.api.voice.stop_voice_listener",
        lambda: stopped.append(True),
    )

    response = api_client.put("/api/voice/mode", json={"enabled": False})

    assert response.status_code == 200
    assert response.json() == {"enabled": False}
    assert stopped == [True]

    set_voice_mode_enabled(False)


def test_voice_mode_get_reflects_state(api_client) -> None:
    """
    Verify that GET /api/voice/mode returns the current enabled state.

    Returns:
        None.
    """
    from app.voice.mode import set_voice_mode_enabled

    set_voice_mode_enabled(True)
    response = api_client.get("/api/voice/mode")

    assert response.status_code == 200
    assert response.json() == {"enabled": True}

    set_voice_mode_enabled(False)


def test_voice_status_input_enabled_matches_mode(api_client, monkeypatch) -> None:
    """
    Verify that voice status reflects runtime mode and listener state.

    Returns:
        None.
    """
    from app.voice.mode import set_voice_mode_enabled

    set_voice_mode_enabled(True)
    _patch_voice_service(
        monkeypatch,
        status=lambda: {
            "available": True,
            "backend": "glados",
            "detail": "GLaDOS voice is ready.",
        },
    )
    monkeypatch.setattr("app.api.voice.is_local_listener_running", lambda: True)

    response = api_client.get("/api/voice/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["input_enabled"] is True
    assert payload["listening"] is True

    set_voice_mode_enabled(False)


def test_audio_to_wav_bytes_applies_volume() -> None:
    """
    Verify that wav synthesis scales samples by volume.

    Returns:
        None.
    """
    from app.voice.service import _audio_to_wav_bytes

    full = _audio_to_wav_bytes([1.0, -1.0], 22050, volume=1.0)
    quiet = _audio_to_wav_bytes([1.0, -1.0], 22050, volume=0.5)

    assert full != quiet


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
