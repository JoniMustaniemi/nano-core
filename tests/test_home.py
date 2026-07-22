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
    assert 'id="brains-clear"' in response.text
    assert "Stored data" in response.text
    assert "Standby" in response.text
    assert "Working" in response.text
    assert "Listening" in response.text
    assert "Type to Nano..." in response.text
    assert "Start Listening" in response.text
    assert "Stop Audio" not in response.text
    assert "Voice on standby." in response.text
    assert 'href="/static/home.css?v=working-status-text-1"' in response.text
    assert 'src="/static/home.js?v=working-status-text-1"' in response.text
    assert 'id="activity-status"' in response.text
    assert "Enter to send" in response.text
    assert 'id="commands-toggle"' in response.text
    assert 'id="commands-drawer"' in response.text
    assert "Commands" in response.text
    assert 'aria-label="Copy answer"' in response.text
    assert "Copy Answer" not in response.text


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
    assert "await playVoice(answerText, { pauseRecognition: true });" in js_response.text
    assert "voicePlaybackQueue" in js_response.text
    assert "playVoiceNow" in js_response.text
    assert "recognitionPausedForSpeech" in js_response.text
    assert "recognitionRunning" in js_response.text
    assert "waitForRecognitionToStop" in js_response.text
    assert "pauseRecognitionForSpeech" in js_response.text
    assert "returnToWakeDetection" in js_response.text
    assert 'copyAnswerButton.classList.add("copied")' in js_response.text
    assert "activity-status" in css_response.text
    assert "renderActivityStatus" in js_response.text
    assert "resolveActivityHeadline" in js_response.text
    assert "WORKING_HEADLINE_DEFAULT" in js_response.text
    assert 'headline === STANDBY_HEADLINE' in js_response.text
    assert "commands-drawer" in css_response.text
    assert 'fetch("/api/tool-commands")' in js_response.text
    assert "runToolCommand" in js_response.text
    assert "applyActivityEvent" in js_response.text
    assert "applyStatusSnapshot" in js_response.text
    assert 'event.kind !== "state"' in js_response.text
    assert "syncRuntimeStatus" in js_response.text
    assert "inputs-locked" in css_response.text
    assert "isBusy()" in js_response.text
    assert "requestInFlight = false;" in js_response.text
    assert '"hey", "hi"' in js_response.text
    assert '"nana"' in js_response.text
    assert '"i know"' in js_response.text
    assert "clearActivityLog" in js_response.text
    assert 'getElementById("brains-clear")' in js_response.text
    assert "ANSWER_CLEAR_DELAY_MS = 20000" in js_response.text
    assert "announceBootMessage" in js_response.text
    assert 'event.source === "system.boot"' in js_response.text
    assert "formatBusyWakeMessage" in js_response.text
    assert "acknowledgeBusyWake" in js_response.text
    assert "isWorkingOnTask" in js_response.text
    assert "busyWakeAnnouncing" in js_response.text
    assert "if (isWorkingOnTask())" in js_response.text


def test_tool_commands_endpoint_lists_quick_actions() -> None:
    """
    Verify that tool commands endpoint returns UI quick actions.

    Returns:
        None.
    """
    with TestClient(app) as client:
        response = client.get("/api/tool-commands")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 5
    assert any(item["id"] == "check_health" for item in payload)
    assert any(item["message"] == "List my notes." for item in payload)


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
    assert payload["headline"] == "Booting complete."
    assert payload["detail"] == "I'm ready and awake."
    assert any(event["source"] == "system.boot" for event in payload["events"])
