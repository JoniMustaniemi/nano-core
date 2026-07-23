const stateLine = document.getElementById("state-line");
const activityStatus = document.getElementById("activity-status");
const activityStatusText = activityStatus.querySelector(".activity-status-text");
const activityLog = document.getElementById("activity-log");
const brainsClearButton = document.getElementById("brains-clear");
const voiceStatus = document.getElementById("voice-status");
const replyStatus = document.getElementById("reply-status");
const messageBox = document.getElementById("message");
const sendButton = document.getElementById("send");
const audioToggle = document.getElementById("audio-toggle");
const answerOutput = document.getElementById("answer-output");
const voiceAudio = document.getElementById("voice-audio");
const storageLog = document.getElementById("storage-log");
const commandsToggle = document.getElementById("commands-toggle");
const commandsDrawer = document.getElementById("commands-drawer");
const commandsBackdrop = document.getElementById("commands-backdrop");
const commandsClose = document.getElementById("commands-close");
const commandsPanel = document.getElementById("commands-panel");
const commandsList = document.getElementById("commands-list");
const voiceVolumeInput = document.getElementById("voice-volume");
const voiceVolumeValue = document.getElementById("voice-volume-value");
const keyboardToggle = document.getElementById("keyboard-toggle");
const keyboardPanel = document.getElementById("keyboard-panel");
const nanoSheet = document.getElementById("nano-sheet");
const nanoSheetBackdrop = document.getElementById("nano-sheet-backdrop");
const nanoSheetClose = document.getElementById("nano-sheet-close");
const nanoControlsToggle = document.getElementById("nano-controls-toggle");
const nanoTabBrains = document.getElementById("nano-tab-brains");
const nanoTabStorage = document.getElementById("nano-tab-storage");
const nanoPanelBrains = document.getElementById("nano-panel-brains");
const nanoPanelStorage = document.getElementById("nano-panel-storage");
const globeCanvas = document.getElementById("globe-canvas");
const globeMiniCanvas = document.getElementById("globe-mini-canvas");

let currentVoiceUrl = null;
let voicePlaybackQueue = Promise.resolve();
let voiceAvailable = false;
const SpeechRecognitionCtor =
  window.SpeechRecognition || window.webkitSpeechRecognition || null;
let recognition = null;
let listeningEnabled = false;
let listeningForCommand = false;
let recognitionStarting = false;
let recognitionRunning = false;
let requestInFlight = false;
let microphoneStream = null;
let microphoneReady = false;
let pendingGestureStart = false;
let lastHeardTranscript = "";
let wakeAcknowledging = false;
let busyWakeAnnouncing = false;
let recognitionPausedForSpeech = false;
let recognitionStopWaiters = [];
let currentActivitySnapshot = {
  state: "standby",
  headline: "I'm in standby.",
  detail: "Awaiting your input.",
};
const activityStates = ["standby", "working", "error"];
const STANDBY_HEADLINE = "I'm in standby.";
const STANDBY_DETAIL_DEFAULT = "Awaiting your input.";
const LISTENING_HEADLINE_DEFAULT = "I'm listening.";
const WORKING_DETAIL_DEFAULT = "Give me a moment.";
const RECEIVED_DETAIL = "Give me a moment.";
let bootAnnouncementPlayed = false;
let lastActivityEventId = 0;
let activityLogHiddenBeforeId = 0;
let answerClearTimer = null;
let answerRevealTimer = null;
const ANSWER_CLEAR_DELAY_MS = 20000;
const IDLE_RESPONSE = "What can I do for you today?";
const VOICE_VOLUME_STORAGE_KEY = "nano.voiceVolume";
const DEFAULT_VOICE_VOLUME = 0.8;
let keyboardOpen = false;
let nanoSheetOpen = false;
let activeNanoTab = "brains";
let speakingActive = false;

let mainGlobe = null;
let miniGlobe = null;

function initGlobes() {
  if (typeof window.initEssenceOrbs === "function") {
    window.initEssenceOrbs();
    mainGlobe = window.mainGlobe || null;
    miniGlobe = window.miniGlobe || null;
  }
}

function updateGlobeState() {
  let state = getDisplayState();
  if (speakingActive) {
    state = "speaking";
  }
  if (stateLine.textContent === "reconnecting") {
    state = "reconnecting";
  }
  if (mainGlobe) {
    mainGlobe.setState(state);
  }
  if (miniGlobe) {
    miniGlobe.setState(state);
  }
}

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

function formatBootMessage(snapshot) {
  const headline = (snapshot.headline || "").trim();
  const detail = (snapshot.detail || "").trim();
  if (!headline) {
    return "";
  }
  if (detail && detail !== headline && !headline.includes(detail)) {
    return `${headline} ${detail}`;
  }
  return headline;
}

function snapshotHasBootEvent(snapshot) {
  return Array.isArray(snapshot.events) && snapshot.events.some(
    (event) => event.source === "system.boot"
  );
}

async function announceBootMessage(snapshot) {
  if (bootAnnouncementPlayed || !snapshotHasBootEvent(snapshot)) {
    return;
  }
  const message = formatBootMessage(snapshot);
  if (!message) {
    return;
  }
  bootAnnouncementPlayed = true;
  setAnswer(message, { animate: false });
  if (voiceAvailable) {
    await playVoice(message);
  }
}

function formatBusyWakeMessage(snapshot) {
  const headline = (snapshot.headline || "I'm working on something.").trim();
  const detail = (snapshot.detail || "").trim();
  if (detail && detail !== headline && !headline.includes(detail)) {
    return `I'm still working. ${headline} — ${detail}`;
  }
  return `I'm still working. ${headline}`;
}

function isWorkingOnTask() {
  return requestInFlight || currentActivitySnapshot.state === "working";
}

function groupCommands(commands) {
  const groups = new Map();
  for (const command of commands) {
    const category = command.category || "Other";
    if (!groups.has(category)) {
      groups.set(category, []);
    }
    groups.get(category).push(command);
  }
  return Array.from(groups.entries());
}

function renderToolCommands(commands) {
  toolCommands = commands;
  commandsList.replaceChildren();
  for (const [category, items] of groupCommands(commands)) {
    const dropdown = document.createElement("details");
    dropdown.className = "commands-dropdown";

    const summary = document.createElement("summary");
    summary.className = "commands-dropdown-toggle";
    summary.textContent = category;

    const grid = document.createElement("div");
    grid.className = "commands-group-grid";

    for (const command of items) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "command-button";
      button.dataset.commandMessage = command.message;

      const label = document.createElement("span");
      label.className = "command-button-label";
      label.textContent = command.label;

      button.append(label);
      if (command.description) {
        const description = document.createElement("span");
        description.className = "command-button-description";
        description.textContent = command.description;
        button.append(description);
      }

      button.addEventListener("click", () => {
        void runToolCommand(command.message);
      });
      grid.append(button);
    }

    dropdown.append(summary, grid);
    commandsList.append(dropdown);
  }
}

function setCommandButtonsDisabled(disabled) {
  for (const button of commandsList.querySelectorAll(".command-button")) {
    button.disabled = disabled;
  }
}

function isBusy() {
  if (listeningForCommand) {
    return false;
  }
  return requestInFlight || wakeAcknowledging;
}

function getDisplayState() {
  if (requestInFlight || wakeAcknowledging) {
    return "working";
  }
  if (currentActivitySnapshot.state === "working") {
    return "working";
  }
  if (isListeningStateActive()) {
    return "listening";
  }
  return "standby";
}

function updateInputLock() {
  const locked = isBusy();
  messageBox.disabled = locked;
  sendButton.disabled = locked;
  commandsToggle.disabled = locked;
  nanoControlsToggle.disabled = locked;
  keyboardToggle.disabled = locked;
  setCommandButtonsDisabled(locked);
  if (!SpeechRecognitionCtor) {
    audioToggle.disabled = true;
  } else {
    audioToggle.disabled = locked;
  }
  document.body.classList.toggle("inputs-locked", locked);
}

function openCommandsDrawer() {
  if (isBusy()) {
    return;
  }
  commandsDrawer.classList.add("open");
  commandsDrawer.setAttribute("aria-hidden", "false");
  commandsToggle.setAttribute("aria-expanded", "true");
  commandsClose.focus();
}

function closeCommandsDrawer() {
  commandsDrawer.classList.remove("open");
  commandsDrawer.setAttribute("aria-hidden", "true");
  commandsToggle.setAttribute("aria-expanded", "false");
  commandsToggle.focus();
}

async function loadToolCommands() {
  const response = await fetch("/api/tool-commands");
  if (!response.ok) {
    throw new Error("Could not load tool commands.");
  }
  return response.json();
}

async function runToolCommand(message) {
  if (isBusy()) {
    return;
  }
  messageBox.value = message;
  closeCommandsDrawer();
  await submitMessage(message, "command");
  messageBox.value = "";
}

function updateListenButton() {
  if (!SpeechRecognitionCtor) {
    audioToggle.disabled = true;
    audioToggle.classList.remove("active");
    audioToggle.setAttribute("aria-pressed", "false");
    renderState();
    return;
  }
  audioToggle.disabled = false;
  audioToggle.classList.toggle("active", listeningEnabled);
  audioToggle.setAttribute("aria-pressed", listeningEnabled ? "true" : "false");
  renderState();
}

function setVoiceStatus(text) {
  voiceStatus.textContent = text;
  renderState();
}

function isListeningStateActive() {
  return (
    listeningEnabled ||
    recognitionStarting ||
    recognitionRunning ||
    listeningForCommand ||
    wakeAcknowledging
  );
}

function resolveActivityHeadline() {
  const displayState = getDisplayState();
  let headline = (currentActivitySnapshot.headline || "").trim();
  const detail = (currentActivitySnapshot.detail || "").trim();

  if (displayState === "working") {
    if (!headline || headline === STANDBY_HEADLINE) {
      headline = detail || WORKING_DETAIL_DEFAULT;
    }
  } else if (displayState === "listening") {
    if (!headline || headline === STANDBY_HEADLINE) {
      headline = LISTENING_HEADLINE_DEFAULT;
    }
  } else if (!headline) {
    headline = STANDBY_HEADLINE;
  }

  if (detail && detail !== headline && !headline.includes(detail)) {
    return `${headline} — ${detail}`;
  }
  return headline;
}

function renderActivityStatus() {
  activityStatusText.textContent = resolveActivityHeadline();
}

function renderState() {
  const displayState = getDisplayState();
  stateLine.textContent = displayState;
  document.body.dataset.displayState = displayState;
  renderActivityStatus();
  updateGlobeState();
  updateInputLock();
}

function resetVoiceListeningMode() {
  listeningForCommand = false;
}

function normalizeWakeText(text) {
  return text
    .toLowerCase()
    .replace(/[.,!?]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function matchesWakeAlias(candidate) {
  const aliases = [
    "nano",
    "nana",
    "nono",
    "na no",
    "nay no",
    "neh no",
    "i know",
    "i no",
  ];
  return aliases.includes(candidate);
}

function extractWakeCommand(text) {
  const normalized = normalizeWakeText(text);
  const prefixes = ["hey", "hi"];
  const words = normalized.split(" ").filter(Boolean);

  for (let index = 0; index < words.length; index += 1) {
    const word = words[index];
    if (!prefixes.includes(word)) {
      continue;
    }

    const oneWordAlias = words[index + 1] || "";
    if (matchesWakeAlias(oneWordAlias)) {
      const command = words.slice(index + 2).join(" ").trim();
      return {
        heardWakeWord: true,
        command,
      };
    }

    const twoWordAlias = words.slice(index + 1, index + 3).join(" ").trim();
    if (matchesWakeAlias(twoWordAlias)) {
      const command = words.slice(index + 3).join(" ").trim();
      return {
        heardWakeWord: true,
        command,
      };
    }
  }
  return {
    heardWakeWord: false,
    command: "",
  };
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
    updateListenButton();
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
      updateListenButton();
      replyStatus.textContent = "Microphone access was denied.";
      setVoiceStatus("Microphone access was denied.");
      return;
    }
    if (error === "no-speech") {
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
    updateListenButton();
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
    updateListenButton();
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
  updateListenButton();
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
    updateListenButton();
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
  updateListenButton();
  if (recognition) {
    recognition.stop();
  }
  setVoiceStatus("Voice listening stopped.");
}

async function connectMicrophoneOnStartup() {
  if (!SpeechRecognitionCtor) {
    replyStatus.textContent = "This browser does not support voice listening.";
    setVoiceStatus("This browser does not support voice listening.");
    updateListenButton();
    return;
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    replyStatus.textContent = "Microphone access is not available in this browser.";
    setVoiceStatus("Microphone access is not available in this browser.");
    updateListenButton();
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
    updateListenButton();
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
    setAnswer(message);
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
    setAnswer(wakeReply);
    replyStatus.textContent = "I'm listening.";
    await playVoice(wakeReply);
  } catch (error) {
    replyStatus.textContent = error.message;
  } finally {
    wakeAcknowledging = false;
    listeningForCommand = true;
    renderState();
    if (microphoneReady) {
      startVoiceListening("resume", true);
    }
  }
}

function applyProactiveSnapshot(proactive) {
  if (!proactive || typeof proactive !== "object") {
    return;
  }
  if (proactive.waiting_for_presence && proactive.prompt) {
    setAnswer(proactive.prompt);
    void playVoice(proactive.prompt, { resumeListening: false });
    return;
  }
  if (proactive.dismissal) {
    setAnswer(proactive.dismissal);
    void playVoice(proactive.dismissal, { resumeListening: false });
  }
}

function resetStandbySnapshot() {
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: "standby",
    headline: STANDBY_HEADLINE,
    detail: STANDBY_DETAIL_DEFAULT,
  };
  renderState();
}

function applyStatusSnapshot(snapshot) {
  const nextState = activityStates.includes(snapshot.state) ? snapshot.state : "standby";
  const useServerCopy = nextState === "standby" || nextState === "error";
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: nextState,
    headline: useServerCopy
      ? (snapshot.headline || STANDBY_HEADLINE)
      : (snapshot.headline || currentActivitySnapshot.headline),
    detail: useServerCopy
      ? (snapshot.detail ?? STANDBY_DETAIL_DEFAULT)
      : (snapshot.detail ?? currentActivitySnapshot.detail),
  };
  applyProactiveSnapshot(snapshot.proactive);
  renderState();
}

function applyActivityEvent(event) {
  if (event.kind === "log" && (requestInFlight || currentActivitySnapshot.state === "working")) {
    const progressLine = (event.title || "").trim();
    if (progressLine) {
      currentActivitySnapshot = {
        ...currentActivitySnapshot,
        state: "working",
        detail: progressLine,
      };
      renderState();
    }
    return;
  }

  if (event.kind !== "state") {
    return;
  }
  const nextState = activityStates.includes(event.state) ? event.state : "standby";
  const useServerCopy = nextState === "standby" || nextState === "error";
  const nextHeadline = useServerCopy
    ? (event.title || STANDBY_HEADLINE)
    : (event.title || currentActivitySnapshot.headline);
  const nextDetail = useServerCopy
    ? (event.detail ?? STANDBY_DETAIL_DEFAULT)
    : (event.detail ?? currentActivitySnapshot.detail);
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: nextState,
    headline: nextHeadline,
    detail: nextDetail,
  };
  if (event.source === "proactive.presence_gate") {
    void fetchProactiveStatus();
  }
  renderState();
}

async function fetchProactiveStatus() {
  try {
    const response = await fetch("/api/proactive");
    if (!response.ok) {
      return;
    }
    const proactive = await response.json();
    applyProactiveSnapshot(proactive);
  } catch (_error) {
    return;
  }
}

async function syncRuntimeStatus() {
  try {
    const snapshot = await loadSnapshot();
    applyStatusSnapshot(snapshot);
  } catch (error) {
    resetStandbySnapshot();
    replyStatus.textContent = error.message;
  }
}

function formatEvent(event) {
  const stamp = event.created_at
    ? new Date(event.created_at).toLocaleTimeString()
    : "--:--:--";
  const source = event.source || "system";
  const title = event.title || "Activity";
  const detailText = event.detail || event.state || "";
  const detailSuffix = detailText ? `\n    ${detailText}` : "";
  return `[${stamp}] ${source} | ${title}${detailSuffix}`;
}

function trackActivityEventId(event) {
  const eventId = Number(event?.id || 0);
  if (eventId > lastActivityEventId) {
    lastActivityEventId = eventId;
  }
}

function shouldShowActivityEvent(event) {
  const eventId = Number(event?.id || 0);
  return eventId > activityLogHiddenBeforeId;
}

function clearActivityLog() {
  activityLogHiddenBeforeId = lastActivityEventId;
  activityLog.value = "";
}

function refreshEvents(snapshot) {
  const events = Array.isArray(snapshot.events)
    ? snapshot.events
        .slice()
        .reverse()
        .filter((event) => {
          trackActivityEventId(event);
          return shouldShowActivityEvent(event);
        })
    : [];
  activityLog.value = events.map((event) => formatEvent(event)).join("\n\n");
  activityLog.scrollTop = activityLog.scrollHeight;
}

function appendEvent(event) {
  trackActivityEventId(event);
  if (!shouldShowActivityEvent(event)) {
    return;
  }
  const line = formatEvent(event);
  activityLog.value = activityLog.value ? `${activityLog.value}\n\n${line}` : line;
  activityLog.scrollTop = activityLog.scrollHeight;
}

function openKeyboardPanel() {
  if (isBusy()) {
    return;
  }
  keyboardOpen = true;
  keyboardPanel.hidden = false;
  document.body.classList.add("keyboard-open");
  keyboardToggle.querySelector("span").textContent = "Use Voice";
  messageBox.focus();
}

function closeKeyboardPanel() {
  keyboardOpen = false;
  document.body.classList.remove("keyboard-open");
  keyboardPanel.hidden = true;
  keyboardToggle.querySelector("span").textContent = "Use Keyboard";
}

function toggleKeyboardPanel() {
  if (keyboardOpen) {
    closeKeyboardPanel();
  } else {
    openKeyboardPanel();
  }
}

function setNanoTab(tab) {
  activeNanoTab = tab;
  const isBrains = tab === "brains";
  nanoTabBrains.classList.toggle("active", isBrains);
  nanoTabStorage.classList.toggle("active", !isBrains);
  nanoTabBrains.setAttribute("aria-selected", isBrains ? "true" : "false");
  nanoTabStorage.setAttribute("aria-selected", isBrains ? "false" : "true");
  nanoPanelBrains.classList.toggle("active", isBrains);
  nanoPanelStorage.classList.toggle("active", !isBrains);
  nanoPanelBrains.hidden = !isBrains;
  nanoPanelStorage.hidden = isBrains;
}

function openNanoSheet(tab = "brains") {
  if (isBusy()) {
    return;
  }
  nanoSheetOpen = true;
  nanoSheet.classList.add("open");
  nanoSheet.setAttribute("aria-hidden", "false");
  nanoControlsToggle.setAttribute("aria-expanded", "true");
  setNanoTab(tab);
  nanoSheetClose.focus();
}

function closeNanoSheet() {
  nanoSheetOpen = false;
  nanoSheet.classList.remove("open");
  nanoSheet.setAttribute("aria-hidden", "true");
  nanoControlsToggle.setAttribute("aria-expanded", "false");
  nanoControlsToggle.focus();
}

function cancelAnswerReveal() {
  if (answerRevealTimer !== null) {
    window.clearTimeout(answerRevealTimer);
    answerRevealTimer = null;
  }
  answerOutput.classList.remove("rolling");
}

function computeResponseFontSize(length) {
  if (length <= 90) {
    return "clamp(1.35rem, 3.5vw + 0.6rem, 2.6rem)";
  }
  if (length <= 180) {
    return "clamp(1.15rem, 2.8vw + 0.45rem, 2.1rem)";
  }
  if (length <= 320) {
    return "clamp(1rem, 2.2vw + 0.3rem, 1.65rem)";
  }
  if (length <= 480) {
    return "clamp(0.92rem, 1.8vw + 0.2rem, 1.35rem)";
  }
  return "clamp(0.82rem, 1.4vw + 0.15rem, 1.1rem)";
}

function applyResponseTypography(length) {
  answerOutput.style.setProperty("--response-font-size", computeResponseFontSize(length));
}

function revealAnswerRolling(content, onComplete) {
  const tokens = content.match(/\S+\s*/gu) || [content];
  let index = 0;
  answerOutput.textContent = "";
  answerOutput.classList.add("rolling");

  const step = () => {
    if (index >= tokens.length) {
      answerOutput.classList.remove("rolling");
      answerRevealTimer = null;
      if (typeof onComplete === "function") {
        onComplete();
      }
      return;
    }
    answerOutput.textContent += tokens[index];
    index += 1;
    const delay = content.length > 420 ? 18 : content.length > 240 ? 24 : content.length > 120 ? 32 : 42;
    answerRevealTimer = window.setTimeout(step, delay);
  };

  step();
}

function clearAnswerClearTimer() {
  if (answerClearTimer !== null) {
    window.clearTimeout(answerClearTimer);
    answerClearTimer = null;
  }
}

function scheduleAnswerClear() {
  clearAnswerClearTimer();
  answerClearTimer = window.setTimeout(() => {
    answerClearTimer = null;
    setAnswer("", { animate: false });
  }, ANSWER_CLEAR_DELAY_MS);
}

function setAnswer(text, options = {}) {
  const content = text.trim();
  const animate = options.animate !== false;
  clearAnswerClearTimer();
  cancelAnswerReveal();
  if (!content) {
    answerOutput.textContent = IDLE_RESPONSE;
    answerOutput.classList.add("empty");
    applyResponseTypography(IDLE_RESPONSE.length);
    return;
  }
  answerOutput.classList.remove("empty");
  applyResponseTypography(content.length);

  const finish = () => {
    scheduleAnswerClear();
  };

  if (!animate) {
    answerOutput.textContent = content;
    finish();
    return;
  }

  revealAnswerRolling(content, finish);
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
  return Math.min(1, Math.sqrt(sum / voiceAnalyserBuffer.length) * 6.2);
}

function pushVoiceLevelToGlobes(level) {
  if (mainGlobe) {
    mainGlobe.setAudioLevel(level);
  }
  if (miniGlobe) {
    miniGlobe.setAudioLevel(level);
  }
}

function startVoiceLevelMonitor() {
  stopVoiceLevelMonitor();
  const tick = () => {
    pushVoiceLevelToGlobes(measureVoiceLevel());
    voiceLevelFrame = requestAnimationFrame(tick);
  };
  voiceLevelFrame = requestAnimationFrame(tick);
}

function stopVoiceLevelMonitor() {
  if (voiceLevelFrame) {
    cancelAnimationFrame(voiceLevelFrame);
    voiceLevelFrame = null;
  }
  pushVoiceLevelToGlobes(0);
}

async function playVoice(text, options = {}) {
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
  updateGlobeState();
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
    updateGlobeState();
    clearVoiceSource();
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
    lowered.includes("specify the timer duration") ||
    lowered.includes("reply yes to proceed or no to cancel")
  );
}

function armVoiceFollowUp(text) {
  listeningForCommand = true;
  setVoiceStatus(text);
  if (microphoneReady && !listeningEnabled && !recognitionStarting) {
    startVoiceListening("resume", true);
  }
}

function returnToWakeDetection() {
  resetVoiceListeningMode();
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

function renderStorage(snapshot) {
  storageLog.value = JSON.stringify(snapshot, null, 2);
  storageLog.scrollTop = 0;
}

async function loadSnapshot() {
  const response = await fetch("/api/status");
  if (!response.ok) {
    throw new Error("Could not load Nano status.");
  }
  return response.json();
}

async function loadStorage() {
  const response = await fetch("/api/storage");
  if (!response.ok) {
    throw new Error("Could not load storage snapshot.");
  }
  return response.json();
}

async function bootstrap() {
  try {
    const snapshot = await loadSnapshot();
    const storage = await loadStorage();
    applyStatusSnapshot(snapshot);
    refreshEvents(snapshot);
    renderStorage(storage);
    const voiceResponse = await fetch("/api/voice/status");
    if (voiceResponse.ok) {
      const voice = await voiceResponse.json();
      voiceAvailable = Boolean(voice.available);
      if (!voiceAvailable && typeof voice.detail === "string") {
        replyStatus.textContent = voice.detail;
      }
    }
    applyVoiceVolume();
    await announceBootMessage(snapshot);
    const commands = await loadToolCommands();
    renderToolCommands(commands);
    await connectMicrophoneOnStartup();
    const lastEventId = Array.isArray(snapshot.events)
      ? snapshot.events.reduce((maxId, event) => {
          const eventId = Number(event?.id || 0);
          return eventId > maxId ? eventId : maxId;
        }, 0)
      : 0;
    listen(lastEventId);
  } catch (error) {
    replyStatus.textContent = error.message;
  }
}

async function refreshStorage() {
  try {
    const storage = await loadStorage();
    renderStorage(storage);
  } catch (error) {
    replyStatus.textContent = error.message;
  }
}

function listen(lastEventId = 0) {
  const source = new EventSource(`/events?since=${lastEventId}`);
  source.addEventListener("activity", (event) => {
    const payload = JSON.parse(event.data);
    applyActivityEvent(payload);
    appendEvent(payload);
    refreshStorage();
  });
  source.onerror = () => {
    stateLine.textContent = "reconnecting";
    updateGlobeState();
  };
}

async function sendMessage() {
  if (isBusy()) {
    replyStatus.textContent = "I'm still working. Wait for the current answer.";
    return;
  }
  const message = messageBox.value.trim();
  if (!message) {
    replyStatus.textContent = "Write a message first.";
    return;
  }
  await submitMessage(message, "text");
  messageBox.value = "";
}

async function sendRecognizedMessage(message) {
  messageBox.value = message;
  await sendMessage();
}

async function acknowledgeRequest(source) {
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: "working",
    headline: "",
    detail: RECEIVED_DETAIL,
  };
  renderState();
  if (source === "voice") {
    pauseRecognitionForSpeech();
  }
}

async function submitMessage(message, source) {
  requestInFlight = true;
  await acknowledgeRequest(source);
  replyStatus.textContent = source === "voice" ? "Sending voice command..." : "Sending...";
  let answerText = "";
  let requestFailed = false;
  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        mode: "agent",
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Chat request failed.");
    }
    answerText = data.content;
    setAnswer(answerText);
    replyStatus.textContent = "Answer ready.";
    await refreshStorage();
  } catch (error) {
    requestFailed = true;
    replyStatus.textContent = error.message;
    returnToWakeDetection();
  } finally {
    requestInFlight = false;
    await syncRuntimeStatus();
  }

  if (requestFailed || !answerText) {
    return;
  }

  const needsVoiceFollowUp = answerNeedsVoiceFollowUp(answerText);
  if (needsVoiceFollowUp) {
    setVoiceStatus("I need your answer. Listening after I finish speaking.");
    await playVoice(answerText, { pauseRecognition: true });
    armVoiceFollowUp("Listening for your answer.");
    return;
  }

  await playVoice(answerText, { pauseRecognition: true });
  returnToWakeDetection();
}

sendButton.addEventListener("click", sendMessage);
commandsToggle.addEventListener("click", openCommandsDrawer);
commandsClose.addEventListener("click", closeCommandsDrawer);
commandsBackdrop.addEventListener("click", closeCommandsDrawer);
commandsPanel.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeCommandsDrawer();
  }
});
audioToggle.addEventListener("click", () => {
  if (isBusy()) {
    return;
  }
  if (listeningEnabled || recognitionStarting) {
    stopVoiceListening();
    return;
  }
  startVoiceListening();
});
keyboardToggle.addEventListener("click", () => {
  if (isBusy()) {
    return;
  }
  toggleKeyboardPanel();
});
nanoControlsToggle.addEventListener("click", () => {
  if (nanoSheetOpen) {
    closeNanoSheet();
    return;
  }
  openNanoSheet("brains");
});
nanoSheetClose.addEventListener("click", closeNanoSheet);
nanoSheetBackdrop.addEventListener("click", closeNanoSheet);
nanoTabBrains.addEventListener("click", () => setNanoTab("brains"));
nanoTabStorage.addEventListener("click", () => setNanoTab("storage"));
nanoSheet.querySelector(".nano-sheet-panel").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeNanoSheet();
  }
});
messageBox.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (isBusy()) {
      return;
    }
    sendMessage();
  }
  if (event.key === "Escape") {
    closeKeyboardPanel();
  }
});
brainsClearButton.addEventListener("click", clearActivityLog);
window.addEventListener("pointerdown", maybeStartListeningAfterGesture, { passive: true });
window.addEventListener("keydown", maybeStartListeningAfterGesture);
window.addEventListener("beforeunload", () => {
  if (microphoneStream) {
    for (const track of microphoneStream.getTracks()) {
      track.stop();
    }
  }
  if (mainGlobe) {
    mainGlobe.destroy();
  }
  if (miniGlobe) {
    miniGlobe.destroy();
  }
});

window.addEventListener("load", () => {
  requestAnimationFrame(() => {
    initGlobes();
    void initVoiceVolumeControl();
    setAnswer("", { animate: false });
    setVoiceStatus("Voice on standby.");
    updateListenButton();
    bootstrap();
  });
});
