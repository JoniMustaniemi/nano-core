from fastapi.testclient import TestClient

from app.main import app


def test_homepage_shows_standby_ui() -> None:
    """
    Verify that homepage shows standby ui.

    Returns:
        None.
    """
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Nano" in response.text
    assert "Nano's brains" in response.text
    assert "Stored data" in response.text
    assert "Standby" in response.text
    assert "Working" in response.text
    assert "Listening" in response.text
    assert "Type to Nano..." in response.text
    assert "Start Listening" in response.text
    assert "Stop Audio" not in response.text
    assert "Voice standby." in response.text
    assert 'href="/static/home.css?v=state-leds-5"' in response.text
    assert 'src="/static/home.js?v=state-leds-5"' in response.text


def test_homepage_serves_static_assets() -> None:
    """
    Verify that homepage serves static assets.

    Returns:
        None.
    """
    with TestClient(app) as client:
        css_response = client.get("/static/home.css")
        js_response = client.get("/static/home.js")

    assert css_response.status_code == 200
    assert js_response.status_code == 200
    assert "details.brains" in css_response.text
    assert '.state-segment[data-state-segment="standby"]' in css_response.text
    assert "background: var(--state-color);" in css_response.text
    assert "box-shadow: 0 0 0 6px var(--state-glow)" in css_response.text
    assert 'join("\\n\\n")' in js_response.text
    assert 'mode: "agent"' in js_response.text
    assert 'fetch("/api/storage")' in js_response.text
    assert 'Waiting for wake phrase: "hey nano".' in js_response.text
    assert "Hearing:" in js_response.text
    assert "SpeechRecognition" in js_response.text
    assert "getUserMedia" in js_response.text
    assert "Microphone connected." in js_response.text
    assert "Press Start Listening to arm wake phrase detection." in js_response.text
    assert "answerNeedsVoiceFollowUp" in js_response.text
    assert "how long should the timer run" in js_response.text
    assert "Listening for your answer." in js_response.text
    assert "await playVoice(data.content, { pauseRecognition: true });" in js_response.text
    assert "voicePlaybackQueue" in js_response.text
    assert "playVoiceNow" in js_response.text
    assert "recognitionPausedForSpeech" in js_response.text
    assert "recognitionRunning" in js_response.text
    assert "waitForRecognitionToStop" in js_response.text
    assert "pauseRecognitionForSpeech" in js_response.text
    assert "returnToWakeDetection" in js_response.text
    assert "stop-audio" not in js_response.text
    assert "stopAudioButton" not in js_response.text
    assert "if (requestInFlight)" in js_response.text
    assert "requestInFlight = true;\n  renderState();" in js_response.text
    assert '"hey", "hi"' in js_response.text
    assert '"nana"' in js_response.text
    assert '"i know"' in js_response.text
    assert 'fetch("/chat/wake")' in js_response.text


def test_status_endpoint_starts_in_standby() -> None:
    """
    Verify that status endpoint starts in standby.

    Returns:
        None.
    """
    with TestClient(app) as client:
        response = client.get("/api/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "standby"
    assert payload["headline"] == "Nano is in standby."
