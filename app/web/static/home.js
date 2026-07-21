const stateLine = document.getElementById("state-line");
const stateSegments = Array.from(document.querySelectorAll("[data-state-segment]"));
const activityLog = document.getElementById("activity-log");
const voiceStatus = document.getElementById("voice-status");
const replyStatus = document.getElementById("reply-status");
const messageBox = document.getElementById("message");
const sendButton = document.getElementById("send");
const listenButton = document.getElementById("voice-listen");
const copyAnswerButton = document.getElementById("copy-answer");
const answerOutput = document.getElementById("answer-output");
const voiceAudio = document.getElementById("voice-audio");
const brainsPanel = document.querySelector(".brains");
const brainsStatus = document.getElementById("brains-status");
const storagePanel = document.querySelector(".storage");
const storageStatus = document.getElementById("storage-status");
const storageLog = document.getElementById("storage-log");
const commandsToggle = document.getElementById("commands-toggle");
const commandsDrawer = document.getElementById("commands-drawer");
const commandsBackdrop = document.getElementById("commands-backdrop");
const commandsClose = document.getElementById("commands-close");
const commandsPanel = document.getElementById("commands-panel");
const commandsList = document.getElementById("commands-list");

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
let recognitionPausedForSpeech = false;
let recognitionStopWaiters = [];
let currentActivitySnapshot = {
  state: "standby",
  headline: "Nano is in standby.",
  detail: "Ready for the next task.",
};
const activityStates = ["standby", "working", "error"];
let toolCommands = [];

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
    const group = document.createElement("section");
    group.className = "commands-group";

    const title = document.createElement("h3");
    title.className = "commands-group-title";
    title.textContent = category;

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

    group.append(title, grid);
    commandsList.append(group);
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
  setCommandButtonsDisabled(locked);
  if (!SpeechRecognitionCtor) {
    listenButton.disabled = true;
  } else {
    listenButton.disabled = locked;
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
    listenButton.disabled = true;
    listenButton.textContent = "Voice Unavailable";
    listenButton.classList.remove("active");
    renderState();
    return;
  }
  listenButton.disabled = false;
  listenButton.textContent = listeningEnabled ? "Stop Listening" : "Start Listening";
  listenButton.classList.toggle("active", listeningEnabled);
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

function renderState() {
  const displayState = getDisplayState();
  stateLine.textContent = displayState;
  for (const segment of stateSegments) {
    segment.classList.toggle("active", segment.dataset.stateSegment === displayState);
  }
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
    if (!transcript || isBusy()) {
      return;
    }

    if (listeningForCommand) {
      resetVoiceListeningMode();
      setVoiceStatus(`Heard command: ${transcript}`);
      await sendRecognizedMessage(transcript);
      return;
    }

    const wakeMatch = extractWakeCommand(transcript);
    if (!wakeMatch.heardWakeWord) {
      return;
    }

    if (wakeMatch.command) {
      setVoiceStatus(`Wake phrase detected. Heard: ${wakeMatch.command}`);
      await sendRecognizedMessage(wakeMatch.command);
      return;
    }

    await acknowledgeWakePhrase();
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
    setVoiceStatus("Voice standby.");
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
    replyStatus.textContent = "Nano is listening.";
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

function applyStatusSnapshot(snapshot) {
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: activityStates.includes(snapshot.state) ? snapshot.state : "standby",
    headline: snapshot.headline || currentActivitySnapshot.headline,
    detail: snapshot.detail ?? currentActivitySnapshot.detail,
  };
  renderState();
}

function applyActivityEvent(event) {
  if (event.kind !== "state") {
    return;
  }
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: activityStates.includes(event.state) ? event.state : "standby",
    headline: event.title || currentActivitySnapshot.headline,
    detail: event.detail ?? currentActivitySnapshot.detail,
  };
  renderState();
}

async function syncRuntimeStatus() {
  try {
    const snapshot = await loadSnapshot();
    applyStatusSnapshot(snapshot);
  } catch (error) {
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

function refreshEvents(snapshot) {
  const events = Array.isArray(snapshot.events)
    ? snapshot.events.slice().reverse()
    : [];
  activityLog.value = events.map((event) => formatEvent(event)).join("\n\n");
  activityLog.scrollTop = activityLog.scrollHeight;
}

function appendEvent(event) {
  const line = formatEvent(event);
  activityLog.value = activityLog.value ? `${activityLog.value}\n\n${line}` : line;
  activityLog.scrollTop = activityLog.scrollHeight;
}

function setAnswer(text) {
  const content = text.trim();
  if (!content) {
    answerOutput.textContent = "Awaiting signal.";
    answerOutput.classList.add("empty");
    return;
  }
  answerOutput.textContent = content;
  answerOutput.classList.remove("empty");
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
    await voiceAudio.play();
    await waitForVoicePlayback();
  } catch (error) {
    replyStatus.textContent = `Nano answered, but voice playback failed: ${error.message}`;
  } finally {
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
    setVoiceStatus("Voice standby.");
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
  };
}

async function sendMessage() {
  if (isBusy()) {
    replyStatus.textContent = "Nano is still working. Wait for the current answer.";
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

async function submitMessage(message, source) {
  requestInFlight = true;
  renderState();
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
    replyStatus.textContent = "Nano answered.";
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
    setVoiceStatus("Nano needs your answer. Listening after it finishes speaking.");
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
listenButton.addEventListener("click", () => {
  if (isBusy()) {
    return;
  }
  if (listeningEnabled || recognitionStarting) {
    stopVoiceListening();
    return;
  }
  startVoiceListening();
});
copyAnswerButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(answerOutput.textContent);
    copyAnswerButton.classList.add("copied");
    copyAnswerButton.setAttribute("aria-label", "Answer copied");
    copyAnswerButton.title = "Answer copied";
    setTimeout(() => {
      copyAnswerButton.classList.remove("copied");
      copyAnswerButton.setAttribute("aria-label", "Copy answer");
      copyAnswerButton.title = "Copy answer";
    }, 1200);
  } catch (error) {
    replyStatus.textContent = "Could not copy the answer.";
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
});
brainsPanel.addEventListener("toggle", () => {
  brainsStatus.textContent = brainsPanel.open ? "open" : "sealed";
});
storagePanel.addEventListener("toggle", () => {
  storageStatus.textContent = storagePanel.open ? "open" : "sealed";
});
window.addEventListener("pointerdown", maybeStartListeningAfterGesture, { passive: true });
window.addEventListener("keydown", maybeStartListeningAfterGesture);
window.addEventListener("beforeunload", () => {
  if (microphoneStream) {
    for (const track of microphoneStream.getTracks()) {
      track.stop();
    }
  }
});

setAnswer("");
setVoiceStatus("Voice standby.");
updateListenButton();
bootstrap();
