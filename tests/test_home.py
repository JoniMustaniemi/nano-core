from fastapi.testclient import TestClient

from app.main import app

HOME_JS_MODULES = (
    "home-state.js",
    "home-plans.js",
    "home-ui.js",
    "home-voice.js",
    "home-activity.js",
    "home-chat.js",
    "home.js",
)


def _load_home_js(client: TestClient) -> str:
    parts: list[str] = []
    for module in HOME_JS_MODULES:
        response = client.get(f"/static/{module}")
        assert response.status_code == 200
        parts.append(response.text)
    return "\n".join(parts)


def _load_home_css(client: TestClient) -> str:
    layout = client.get("/static/home-layout.css")
    components = client.get("/static/home-components.css")
    assert layout.status_code == 200
    assert components.status_code == 200
    return layout.text + components.text


def test_homepage_shows_standby_ui() -> None:

    """

    Verify that homepage shows standby ui.



    Returns:

        None.

    """

    with TestClient(app) as client:

        response = client.get("/")



    assert response.status_code == 200

    assert 'id="activity-status"' in response.text

    assert 'id="answer-output"' in response.text
    assert 'class="response-zone"' in response.text

    assert "What can I do for you today?" in response.text

    assert 'id="essence-canvas"' in response.text

    assert 'id="essence-mini-canvas"' in response.text

    assert 'id="controls-reveal-zone"' in response.text

    assert 'id="controls-reveal"' in response.text

    assert 'id="keyboard-toggle"' in response.text

    assert "Use Keyboard" in response.text

    assert 'class="bottom-bar"' in response.text
    assert 'class="footer-cluster"' in response.text

    assert 'id="nano-controls-toggle"' in response.text

    assert 'id="audio-toggle"' in response.text

    assert 'id="commands-toggle"' in response.text

    assert 'id="nano-sheet"' in response.text

    assert "Nano's brains" not in response.text

    assert "Brains" in response.text
    assert "Plans" in response.text
    assert 'id="nano-tab-plans"' in response.text
    assert 'id="plans-list"' in response.text
    assert 'id="plans-tab-count"' in response.text
    assert 'id="plan-reader"' in response.text

    assert 'id="brains-clear"' in response.text

    assert "Stored Data" in response.text

    assert "Standby" not in response.text

    assert "Working" not in response.text

    assert "Listening" not in response.text

    assert "Type to Nano..." in response.text

    assert "Start Listening" not in response.text

    assert 'id="voice-status"' in response.text

    assert 'href="/static/home.css?v=controls-toggle-3"' in response.text

    assert 'src="/static/three.min.js?v=0.160.1"' in response.text
    assert 'src="/static/essence_visualizer.js?v=aurora-core-7"' in response.text
    assert 'src="/static/home-state.js?v=controls-toggle-3"' in response.text
    assert 'src="/static/home-plans.js?v=procedural-orb-24"' in response.text
    assert 'src="/static/home.js?v=controls-toggle-1"' in response.text

    assert "Enter to send" in response.text

    assert 'id="commands-drawer"' in response.text
    assert 'id="voice-volume"' in response.text
    assert 'id="voice-volume-value"' in response.text
    assert "Voice settings" in response.text or 'aria-label="Voice settings"' in response.text



def test_homepage_serves_static_assets() -> None:

    """

    Verify that homepage serves static assets.



    Returns:

        None.

    """

    with TestClient(app) as client:
        css_text = _load_home_css(client)
        js_text = _load_home_js(client)
        essence_js_response = client.get("/static/essence_visualizer.js")

    assert ".nano-sheet" in css_text

    assert ".bottom-bar" in css_text

    assert ".footer-cluster" in css_text

    assert ".essence-zone" in css_text

    assert ".controls-reveal-zone" in css_text

    assert ".controls-reveal" in css_text

    assert "controls-hidden" in css_text

    assert "@keyframes blink" in css_text

    assert 'join("\\n\\n")' in js_text

    assert 'mode: "agent"' in js_text

    assert ".plan-card" in css_text
    assert 'fetch("/api/improvement-plans")' in js_text

    assert 'Waiting for wake phrase: "hey nano".' in js_text

    assert "Hearing:" in js_text

    assert "SpeechRecognition" in js_text

    assert "getUserMedia" in js_text

    assert "Microphone connected." in js_text

    assert "Press Start Listening to arm wake phrase detection." in js_text

    assert "answerNeedsVoiceFollowUp" in js_text

    assert "how long should the timer run" in js_text

    assert "Listening for your answer." in js_text

    assert "await playVoice(answerText, { pauseRecognition: true });" in js_text

    assert "voicePlaybackQueue" in js_text

    assert "playVoiceNow" in js_text

    assert "initVoiceVolumeControl" in js_text

    assert "VOICE_VOLUME_STORAGE_KEY" in js_text

    assert "applyVoiceVolume" in js_text
    assert 'fetch("/api/voice/volume"' in js_text
    assert "revealAnswerRolling" in js_text
    assert "computeResponseFontSize" in js_text

    assert "recognitionPausedForSpeech" in js_text

    assert "recognitionRunning" in js_text

    assert "waitForRecognitionToStop" in js_text

    assert "pauseRecognitionForSpeech" in js_text

    assert "returnToWakeDetection" in js_text

    assert ".activity-status" in css_text

    assert "renderActivityStatus" in js_text

    assert "resolveActivityHeadline" in js_text

    assert "WORKING_DETAIL_DEFAULT" in js_text

    assert "STANDBY_DETAIL_DEFAULT" in js_text

    assert "resetStandbySnapshot" in js_text

    assert "useServerCopy" in js_text

    submit_block = js_text.split("async function submitMessage(message, source)")[1]

    submit_block = submit_block.split("renderState();")[0]

    assert 'state: "working"' not in submit_block

    assert 'headline === STANDBY_HEADLINE' in js_text

    assert "commands-drawer" in css_text

    assert ".voice-volume" in css_text

    assert "matchControlsUiCommand" in js_text

    assert "completeUiCommand" in js_text

    assert "toggleControlsHidden" in js_text

    assert 'fetch("/api/tool-commands")' in js_text

    assert "runToolCommand" in js_text

    assert "applyActivityEvent" in js_text

    assert "runtime.long_task_progress" in js_text

    assert "--text-primary" in css_text
    assert "plans-tab-count" in css_text
    assert "updatePlansTabCount" in js_text

    assert "formatProgressAnnouncement" in js_text

    assert 'playVoice(message, { resumeListening: false })' in js_text

    assert "applyStatusSnapshot" in js_text

    assert 'event.kind !== "state"' in js_text

    assert "syncRuntimeStatus" in js_text

    assert "inputs-locked" in css_text

    assert "isBusy()" in js_text

    assert "requestInFlight = false;" in js_text

    assert '"hey", "hi"' in js_text

    assert '"nana"' in js_text

    assert '"i know"' in js_text

    assert "clearActivityLog" in js_text

    assert 'getElementById("brains-clear")' in js_text

    assert "ANSWER_CLEAR_DELAY_MS = 20000" in js_text

    assert "resumeAnswerClearAfterSpeech" in js_text

    assert "bypassSpeechGuard" in js_text

    assert "announceBootMessage" in js_text

    assert 'event.source === "system.boot"' in js_text

    assert "formatBusyWakeMessage" in js_text

    assert "acknowledgeBusyWake" in js_text

    assert "isWorkingOnTask" in js_text

    assert "busyWakeAnnouncing" in js_text

    assert "if (isWorkingOnTask())" in js_text

    assert "EssenceVisualizer" in essence_js_response.text

    assert "ESSENCE_STATES" in essence_js_response.text

    assert "auroraBands" in essence_js_response.text
    assert "measureVoiceLevel" in js_text

    assert "toggleKeyboardPanel" in js_text

    assert "openNanoSheet" in js_text

    assert 'getElementById("audio-toggle")' in js_text





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

    assert any(item["id"] == "wipe_data" for item in payload)

    assert any(item["id"] == "toggle_controls" for item in payload)

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

