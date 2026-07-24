function formatVoiceVolumePercent(volume) {
  return `${Math.round(volume * 100)}%`;
}

function loadVoiceVolume() {
  try {
    const stored = window.localStorage.getItem(VOICE_VOLUME_STORAGE_KEY);
    if (stored === null) {
      return DEFAULT_VOICE_VOLUME;
    }
    const parsed = Number(stored);
    if (!Number.isFinite(parsed)) {
      return DEFAULT_VOICE_VOLUME;
    }
    return Math.min(1, Math.max(0, parsed));
  } catch (_error) {
    return DEFAULT_VOICE_VOLUME;
  }
}

function saveVoiceVolume(volume) {
  try {
    window.localStorage.setItem(VOICE_VOLUME_STORAGE_KEY, String(volume));
  } catch (_error) {
    return;
  }
}

function applyVoiceVolume(volume = loadVoiceVolume()) {
  const clamped = Math.min(1, Math.max(0, volume));
  voiceAudio.volume = clamped;
  if (voiceVolumeInput) {
    voiceVolumeInput.value = String(Math.round(clamped * 100));
    voiceVolumeInput.disabled = !voiceAvailable;
  }
  if (voiceVolumeValue) {
    voiceVolumeValue.textContent = formatVoiceVolumePercent(clamped);
  }
  return clamped;
}

async function syncVoiceVolumeToServer(volume) {
  try {
    const response = await fetch("/api/voice/volume", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ volume }),
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    if (typeof payload.volume === "number") {
      saveVoiceVolume(payload.volume);
    }
  } catch (_error) {
    return;
  }
}

function setVoiceVolumeFromInput(percent) {
  const volume = applyVoiceVolume(percent / 100);
  saveVoiceVolume(volume);
  void syncVoiceVolumeToServer(volume);
}

async function initVoiceVolumeControl() {
  applyVoiceVolume();
  await syncVoiceVolumeToServer(loadVoiceVolume());
  if (!voiceVolumeInput) {
    return;
  }
  voiceVolumeInput.addEventListener("input", () => {
    setVoiceVolumeFromInput(Number(voiceVolumeInput.value));
  });
}

function ensureRecognition() {
  if (!SpeechRecognitionCtor || recognition) {
    return recognition;
  }
  recognition = new SpeechRecognitionCtor();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onstart = () => {
    recognitionRunning = true;
    recognitionStarting = false;
    pendingGestureStart = false;
    setVoiceStatus(
      listeningForCommand
        ? "Wake phrase detected. Listening for your command."
        : 'Waiting for wake phrase: "hey nano".'
    );
    syncVoiceListeningState();
  };

  recognition.onresult = async (event) => {
    let finalTranscript = "";
    let interimTranscript = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      if (result.isFinal) {
        finalTranscript += result[0].transcript;
      } else {
        interimTranscript += result[0].transcript;
      }
    }

    const heardText = (finalTranscript || interimTranscript).trim();
    if (heardText && listeningForCommand) {
      lastHeardTranscript = heardText;
      setVoiceStatus(`Hearing: ${heardText}`);
    }

    const transcript = finalTranscript.trim();
    if (!transcript) {
      return;
    }

    if (listeningForCommand) {
      if (isBusy()) {
        return;
      }
      if (waitingForPresence) {
        waitingForPresence = false;
      }
      waitingForFollowUp = false;
      resetVoiceListeningMode();
      setVoiceStatus(`Heard command: ${transcript}`);
      await sendRecognizedMessage(transcript);
      return;
    }

    if (wakeAcknowledging || busyWakeAnnouncing) {
      return;
    }

    const wakeMatch = extractWakeCommand(transcript);
    if (wakeMatch.heardWakeWord) {
      if (isWorkingOnTask()) {
        await acknowledgeBusyWake();
        return;
      }
      if (wakeMatch.command) {
        setVoiceStatus(`Wake phrase detected. Heard: ${wakeMatch.command}`);
        await sendRecognizedMessage(wakeMatch.command);
        return;
      }
      await acknowledgeWakePhrase();
      return;
    }

    if (isBusy()) {
      return;
    }
  };

  recognition.onerror = (event) => {
    const error = event.error || "voice recognition failed";
    if (error === "not-allowed" || error === "service-not-allowed") {
      listeningEnabled = false;
      recognitionStarting = false;
      resetVoiceListeningMode();
      syncVoiceListeningState();
      replyStatus.textContent = "Microphone access was denied.";
      setVoiceStatus("Microphone access was denied.");
      return;
    }
    if (error === "no-speech") {
      if (waitingForPresence || waitingForFollowUp) {
        setVoiceStatus(
          waitingForPresence
            ? "Still waiting. Reply yes or no if you are there."
            : "Still waiting for your answer."
        );
        return;
      }
      if (listeningForCommand) {
        setVoiceStatus("I heard the wake phrase, but not the command.");
        resetVoiceListeningMode();
      } else if (listeningEnabled) {
        setVoiceStatus('Waiting for wake phrase: "hey nano".');
      }
      return;
    }
    setVoiceStatus(`Voice listening error: ${error}`);
  };

  recognition.onend = () => {
    recognitionRunning = false;
    recognitionStarting = false;
    resolveRecognitionStopWaiters();
    if (recognitionPausedForSpeech) {
      return;
    }
    if (wakeAcknowledging) {
      return;
    }
    if (isWaitingForUserAnswer() && microphoneReady) {
      listeningEnabled = true;
      listeningForCommand = true;
      try {
        recognition.start();
        recognitionStarting = true;
        setVoiceStatus(directAnswerListenStatus());
      } catch (error) {
        pendingGestureStart = true;
        setVoiceStatus("Microphone is connected. Press Start Listening to reply.");
      }
      return;
    }
    if (listeningEnabled) {
      try {
        recognition.start();
        recognitionStarting = true;
      } catch (error) {
        pendingGestureStart = true;
        setVoiceStatus(
          "Microphone is connected. Press Start Listening to arm wake phrase detection."
        );
      }
      return;
    }
    resetVoiceListeningMode();
    setVoiceStatus("Voice on standby.");
    syncVoiceListeningState();
  };

  return recognition;
}

function resolveRecognitionStopWaiters() {
  const waiters = recognitionStopWaiters;
  recognitionStopWaiters = [];
  for (const resolve of waiters) {
    resolve();
  }
}

function waitForRecognitionToStop(timeoutMs = 1200) {
  if (!recognitionRunning && !recognitionStarting) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const timeoutId = window.setTimeout(() => {
      recognitionStopWaiters = recognitionStopWaiters.filter(
        (waiter) => waiter !== finish
      );
      resolve();
    }, timeoutMs);
    function finish() {
      window.clearTimeout(timeoutId);
      resolve();
    }
    recognitionStopWaiters.push(finish);
  });
}

function startVoiceListening(mode = "manual", preserveCommandMode = false) {
  if (!preserveCommandMode && isBusy()) {
    return;
  }
  if (!SpeechRecognitionCtor) {
    replyStatus.textContent = "This browser does not support voice listening.";
    setVoiceStatus("This browser does not support voice listening.");
    syncVoiceListeningState();
    return;
  }
  if (!microphoneReady) {
    replyStatus.textContent = "Microphone is not connected yet.";
    setVoiceStatus("Microphone is not connected yet.");
    return;
  }
  const instance = ensureRecognition();
  if (!instance) {
    return;
  }
  listeningEnabled = true;
  if (!preserveCommandMode) {
    resetVoiceListeningMode();
  }
  syncVoiceListeningState();
  if (recognitionRunning || recognitionStarting) {
    setVoiceStatus(
      listeningForCommand
        ? "Wake phrase detected. Listening for your command."
        : 'Waiting for wake phrase: "hey nano".'
    );
    return;
  }
  setVoiceStatus('Arming wake phrase detection for "hey nano".');
  try {
    instance.start();
    recognitionStarting = true;
  } catch (error) {
    listeningEnabled = false;
    recognitionStarting = false;
    syncVoiceListeningState();
    if (mode === "auto") {
      pendingGestureStart = true;
      setVoiceStatus(
        "Microphone is connected. Press Start Listening to arm wake phrase detection."
      );
      return;
    }
    setVoiceStatus(`Could not start voice listening: ${error.message}`);
  }
}

function stopVoiceListening() {
  listeningEnabled = false;
  recognitionStarting = false;
  recognitionRunning = false;
  resetVoiceListeningMode();
  wakeAcknowledging = false;
  syncVoiceListeningState();
  if (recognition) {
    recognition.stop();
  }
  setVoiceStatus("Voice listening stopped.");
}

async function connectMicrophoneOnStartup() {
  if (!SpeechRecognitionCtor) {
    replyStatus.textContent = "This browser does not support voice listening.";
    setVoiceStatus("This browser does not support voice listening.");
    syncVoiceListeningState();
    return;
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    replyStatus.textContent = "Microphone access is not available in this browser.";
    setVoiceStatus("Microphone access is not available in this browser.");
    syncVoiceListeningState();
    return;
  }
  try {
    microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    microphoneReady = true;
    setVoiceStatus("Microphone connected.");
    startVoiceListening("auto");
  } catch (error) {
    replyStatus.textContent = "Microphone access was not granted.";
    setVoiceStatus("Microphone access was not granted.");
    syncVoiceListeningState();
  }
}

function maybeStartListeningAfterGesture() {
  if (!pendingGestureStart || !microphoneReady || listeningEnabled || recognitionStarting) {
    return;
  }
  startVoiceListening("gesture");
}

async function requestWakeAcknowledgement() {
  const response = await fetch("/chat/wake");
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Wake acknowledgment failed.");
  }
  return data.content;
}

async function acknowledgeBusyWake() {
  if (busyWakeAnnouncing || wakeAcknowledging) {
    return;
  }
  busyWakeAnnouncing = true;
  try {
    let snapshot = currentActivitySnapshot;
    try {
      const fresh = await loadSnapshot();
      snapshot = {
        ...snapshot,
        state: activityStates.includes(fresh.state) ? fresh.state : snapshot.state,
        headline: fresh.headline || snapshot.headline,
        detail: fresh.detail ?? snapshot.detail,
      };
    } catch (_error) {
      // Fall back to the cached activity snapshot.
    }
    const message = formatBusyWakeMessage(snapshot);
    if (!message) {
      return;
    }
    setAnswer(message, { deferClearUntilSpeech: true });
    replyStatus.textContent = "Still working on the current task.";
    setVoiceStatus("Wake phrase detected while working.");
    await playVoice(message, { pauseRecognition: true });
  } finally {
    busyWakeAnnouncing = false;
  }
}

async function acknowledgeWakePhrase() {
  if (wakeAcknowledging || isBusy()) {
    return;
  }
  wakeAcknowledging = true;
  renderState();
  listeningEnabled = false;
  recognitionStarting = false;
  if (recognition) {
    recognition.stop();
  }
  setVoiceStatus("Wake phrase detected.");
  try {
    const wakeReply = await requestWakeAcknowledgement();
    setAnswer(wakeReply, { deferClearUntilSpeech: true });
    replyStatus.textContent = "I'm listening.";
    await playVoice(wakeReply);
  } catch (error) {
    replyStatus.textContent = error.message;
  } finally {
    wakeAcknowledging = false;
    waitingForFollowUp = false;
    listeningForCommand = true;
    renderState();
    if (microphoneReady) {
      startVoiceListening("resume", true);
    }
  }
}

let voiceAudioContext = null;
let voiceAnalyser = null;
let voiceAnalyserBuffer = null;
let voiceLevelFrame = null;

function ensureVoiceAnalyser() {
  if (voiceAnalyser) {
    return voiceAnalyser;
  }
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) {
    return null;
  }
  voiceAudioContext = new AudioCtx();
  const source = voiceAudioContext.createMediaElementSource(voiceAudio);
  voiceAnalyser = voiceAudioContext.createAnalyser();
  voiceAnalyser.fftSize = 512;
  voiceAnalyser.smoothingTimeConstant = 0.8;
  source.connect(voiceAnalyser);
  voiceAnalyser.connect(voiceAudioContext.destination);
  voiceAnalyserBuffer = new Uint8Array(voiceAnalyser.fftSize);
  return voiceAnalyser;
}

async function resumeVoiceAudioContext() {
  ensureVoiceAnalyser();
  if (voiceAudioContext && voiceAudioContext.state === "suspended") {
    await voiceAudioContext.resume();
  }
}

function measureVoiceLevel() {
  if (!voiceAnalyser || !voiceAnalyserBuffer) {
    return 0;
  }
  voiceAnalyser.getByteTimeDomainData(voiceAnalyserBuffer);
  let sum = 0;
  for (let index = 0; index < voiceAnalyserBuffer.length; index += 1) {
    const sample = (voiceAnalyserBuffer[index] - 128) / 128;
    sum += sample * sample;
  }
  return Math.min(1, Math.sqrt(sum / voiceAnalyserBuffer.length) * 4.0);
}

function pushVoiceLevelToEssence(level) {
  if (mainEssence) {
    mainEssence.setAudioLevel(level);
  }
}

function startVoiceLevelMonitor() {
  stopVoiceLevelMonitor();
  const tick = () => {
    pushVoiceLevelToEssence(measureVoiceLevel());
    voiceLevelFrame = requestAnimationFrame(tick);
  };
  voiceLevelFrame = requestAnimationFrame(tick);
}

function stopVoiceLevelMonitor() {
  if (voiceLevelFrame) {
    cancelAnimationFrame(voiceLevelFrame);
    voiceLevelFrame = null;
  }
  pushVoiceLevelToEssence(0);
}

async function playVoice(text, options = {}) {
  const content = (text || "").trim();
  if (content) {
    setAnswer(content, {
      animate: false,
      deferClearUntilSpeech: Boolean(voiceAvailable),
    });
  }
  if (!voiceAvailable || !content) {
    resumeAnswerClearAfterSpeech();
    return;
  }
  const playback = voicePlaybackQueue.then(() => playVoiceNow(text, options));
  voicePlaybackQueue = playback.catch(() => undefined);
  return playback;
}

async function playVoiceNow(text, options = {}) {
  if (!voiceAvailable || !text.trim()) {
    return;
  }
  const pauseRecognition = Boolean(options.pauseRecognition);
  const shouldResumeRecognition = pauseRecognition && listeningEnabled;
  const preserveCommandMode = listeningForCommand;
  if (shouldResumeRecognition && recognition) {
    await pauseRecognitionForSpeech();
  }
  clearVoiceSource();
  speakingActive = true;
  updateEssenceState();
  try {
    const response = await fetch("/api/voice", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail || "Voice playback failed.");
    }
    const blob = await response.blob();
    currentVoiceUrl = URL.createObjectURL(blob);
    voiceAudio.src = currentVoiceUrl;
    applyVoiceVolume();
    await resumeVoiceAudioContext();
    await voiceAudio.play();
    startVoiceLevelMonitor();
    await waitForVoicePlayback();
  } catch (error) {
    replyStatus.textContent = `I answered, but voice playback failed: ${error.message}`;
  } finally {
    stopVoiceLevelMonitor();
    speakingActive = false;
    updateEssenceState();
    clearVoiceSource();
    resumeAnswerClearAfterSpeech();
    if (shouldResumeRecognition && microphoneReady) {
      listeningForCommand = preserveCommandMode;
      recognitionPausedForSpeech = false;
      startVoiceListening("resume", preserveCommandMode);
    } else {
      recognitionPausedForSpeech = false;
    }
  }
}

async function pauseRecognitionForSpeech() {
  if (!recognition || (!recognitionRunning && !recognitionStarting)) {
    return;
  }
  recognitionPausedForSpeech = true;
  listeningEnabled = false;
  recognitionStarting = false;
  try {
    recognition.stop();
  } catch (error) {
    recognitionRunning = false;
    resolveRecognitionStopWaiters();
    return;
  }
  await waitForRecognitionToStop();
}

function clearVoiceSource() {
  if (currentVoiceUrl) {
    URL.revokeObjectURL(currentVoiceUrl);
    currentVoiceUrl = null;
  }
  voiceAudio.removeAttribute("src");
}

function waitForVoicePlayback() {
  return new Promise((resolve) => {
    if (voiceAudio.ended || voiceAudio.paused) {
      resolve();
      return;
    }
    voiceAudio.addEventListener("ended", resolve, { once: true });
    voiceAudio.addEventListener("error", resolve, { once: true });
  });
}

function answerNeedsVoiceFollowUp(text) {
  const lowered = text.toLowerCase();
  return (
    lowered.includes("how long should the timer run") ||
    lowered.includes("didn't catch a duration") ||
    lowered.includes("reply yes to proceed or no to cancel")
  );
}

const PRESENCE_LISTEN_STATUS = "Are you there? Reply yes or no.";

function pendingListenStatus(kind) {
  const labels = {
    timer_duration: "How long should the timer run? Reply with a duration.",
    wipe_confirmation: "Reply yes to proceed or no to cancel.",
    note_name: "What should I name the note?",
    note_content: "What should the note say?",
    note_selection: "Which note did you mean?",
  };
  return labels[kind] || "Listening for your answer.";
}

function directAnswerListenStatus() {
  if (waitingForPresence) {
    return PRESENCE_LISTEN_STATUS;
  }
  return "Listening for your answer.";
}

function ensureDirectAnswerListening(statusText) {
  listeningForCommand = true;
  if (!waitingForPresence) {
    waitingForFollowUp = true;
  }
  setVoiceStatus(statusText || directAnswerListenStatus());
  if (microphoneReady) {
    startVoiceListening("resume", true);
  }
  renderState();
  if (!speakingActive) {
    scheduleAnswerTimeout();
  } else {
    answerTimeoutPending = true;
  }
}

async function enterPresenceListenMode(prompt) {
  const text = (prompt || "Are you there?").trim();
  waitingForFollowUp = false;
  if (waitingForPresence) {
    if (!listeningForCommand && microphoneReady) {
      ensureDirectAnswerListening(PRESENCE_LISTEN_STATUS);
      return;
    }
    return;
  }

  waitingForPresence = true;
  setAnswer(text, { animate: false, deferClearUntilSpeech: Boolean(voiceAvailable && text) });
  renderState();
  try {
    if (voiceAvailable && text) {
      await playVoice(text, { pauseRecognition: true });
    }
  } finally {
    if (!waitingForPresence) {
      return;
    }
    ensureDirectAnswerListening(PRESENCE_LISTEN_STATUS);
  }
}

function exitPresenceListenMode() {
  if (!waitingForPresence) {
    return;
  }
  waitingForPresence = false;
  resetVoiceListeningMode();
  renderState();
}

async function handlePresenceDismissal(message) {
  const text = (message || "").trim();
  exitPresenceListenMode();
  if (text) {
    setAnswer(text, {
      animate: false,
      deferClearUntilSpeech: Boolean(voiceAvailable),
    });
    if (voiceAvailable) {
      await playVoice(text, { pauseRecognition: true });
    }
  }
  returnToWakeDetection();
}

function armVoiceFollowUp(text) {
  ensureDirectAnswerListening(text || "Listening for your answer.");
}

function returnToWakeDetection() {
  if (isWaitingForUserAnswer()) {
    ensureDirectAnswerListening();
    return;
  }
  resetVoiceListeningMode();
  waitingForFollowUp = false;
  if (microphoneReady && !listeningEnabled && !recognitionStarting) {
    startVoiceListening("resume");
    return;
  }
  if (listeningEnabled) {
    setVoiceStatus('Waiting for wake phrase: "hey nano".');
  } else {
    setVoiceStatus("Voice on standby.");
  }
}

