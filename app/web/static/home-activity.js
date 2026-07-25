function applyProactiveSnapshot(proactive) {
  if (!proactive || typeof proactive !== "object") {
    return;
  }
  if (proactive.waiting_for_presence && proactive.prompt) {
    void enterPresenceListenMode(proactive.prompt);
    return;
  }
  if (proactive.dismissal) {
    if (proactive.dismissal === lastHandledDismissal) {
      return;
    }
    lastHandledDismissal = proactive.dismissal;
    void handlePresenceDismissal(proactive.dismissal);
    return;
  }
  if (lastHandledDismissal && !proactive.dismissal) {
    lastHandledDismissal = null;
  }
  if (waitingForPresence) {
    exitPresenceListenMode();
    returnToWakeDetection();
  }
}

function resetStandbySnapshot() {
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: "standby",
    headline: currentStandbyGreeting || STANDBY_HEADLINE,
    detail: null,
  };
  renderState();
  void refreshStandbyGreeting();
}

async function refreshStandbyGreeting(options = {}) {
  try {
    const response = await fetch("/api/greeting");
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    const greeting = (payload.greeting || "").trim();
    if (!greeting) {
      return;
    }
    currentStandbyGreeting = greeting;
    if (
      currentActivitySnapshot.state === "standby" &&
      !resolveListeningIntent() &&
      !hasCustomStandbyActivityCopy()
    ) {
      currentActivitySnapshot = {
        ...currentActivitySnapshot,
        headline: greeting,
        detail: null,
      };
    }
    renderState();
    const speakOnce = options.speakOnce === true;
    const shouldSpeak =
      speakOnce &&
      voiceAvailable &&
      !window.sessionStorage.getItem(GREETING_SPOKEN_KEY);
    if (shouldSpeak) {
      try {
        window.sessionStorage.setItem(GREETING_SPOKEN_KEY, "1");
        await playVoice(greeting, { pauseRecognition: true });
      } catch (_error) {
        window.sessionStorage.removeItem(GREETING_SPOKEN_KEY);
        setAnswer(greeting, { animate: false });
      }
      return;
    }
    setAnswer(greeting, { animate: false });
  } catch (_error) {
    return;
  }
}

function applyPendingSnapshot(pending, proactive) {
  if (!pending || typeof pending !== "object") {
    if (!waitingForPresence) {
      waitingForFollowUp = false;
    }
    clearAnswerTimeoutTimer();
    answerTimeoutPending = false;
    return;
  }
  const kind = pending.kind;
  if (!kind) {
    if (!waitingForPresence) {
      waitingForFollowUp = false;
    }
    clearAnswerTimeoutTimer();
    answerTimeoutPending = false;
    return;
  }
  if (kind === "presence_check") {
    return;
  }
  ensureDirectAnswerListening(pendingListenStatus(kind));
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
    task_timer: snapshot.task_timer ?? null,
  };
  if (
    nextState === "standby" &&
    snapshot.headline &&
    snapshot.headline !== STANDBY_HEADLINE
  ) {
    currentStandbyGreeting = String(snapshot.headline);
  }
  applyProactiveSnapshot(snapshot.proactive);
  applyPendingSnapshot(snapshot.pending, snapshot.proactive);
  syncTaskWaitTimer(snapshot.task_timer ?? null);
  renderState();
}

function formatTaskWaitClock(seconds) {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const remainder = total % 60;
  return `${minutes}:${String(remainder).padStart(2, "0")}`;
}

function formatTaskTimerElapsedPhrase(elapsedSeconds, expectedSeconds) {
  if (elapsedSeconds < 60) {
    return `about ${Math.max(1, elapsedSeconds)} seconds in`;
  }
  const elapsedMinutes = Math.max(1, Math.round(elapsedSeconds / 60));
  const expectedMinutes = Math.max(1, Math.round(expectedSeconds / 60));
  return `about ${elapsedMinutes} minute${elapsedMinutes === 1 ? "" : "s"} in, up to ${expectedMinutes} minute${expectedMinutes === 1 ? "" : "s"}`;
}

function getTaskTimerElapsedSeconds(taskTimer) {
  if (!taskTimer || !taskTimer.started_at) {
    return 0;
  }
  const startedAt = Date.parse(taskTimer.started_at);
  if (Number.isNaN(startedAt)) {
    return 0;
  }
  return Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
}

function renderTaskWaitTimer(taskTimer) {
  if (!taskWaitTimer || !taskWaitLabel || !taskWaitClock) {
    return;
  }
  if (!taskTimer || !taskTimer.label) {
    taskWaitTimer.hidden = true;
    return;
  }
  const elapsedSeconds = getTaskTimerElapsedSeconds(taskTimer);
  const expectedSeconds = Number(taskTimer.expected_seconds) || 0;
  taskWaitLabel.textContent = taskTimer.label;
  if (expectedSeconds > 0 && elapsedSeconds >= expectedSeconds) {
    taskWaitClock.textContent = `${formatTaskWaitClock(elapsedSeconds)} / ${formatTaskWaitClock(expectedSeconds)}+`;
  } else {
    taskWaitClock.textContent = `${formatTaskWaitClock(elapsedSeconds)} / ${formatTaskWaitClock(expectedSeconds)}`;
  }
  taskWaitTimer.hidden = false;
}

function clearTaskWaitTimerInterval() {
  if (taskWaitClockInterval !== null) {
    window.clearInterval(taskWaitClockInterval);
    taskWaitClockInterval = null;
  }
}

function syncTaskWaitTimer(taskTimer) {
  currentTaskTimer = taskTimer && taskTimer.label ? taskTimer : null;
  clearTaskWaitTimerInterval();
  renderTaskWaitTimer(currentTaskTimer);
  if (!currentTaskTimer) {
    return;
  }
  taskWaitClockInterval = window.setInterval(() => {
    renderTaskWaitTimer(currentTaskTimer);
  }, 1000);
}

function formatProgressAnnouncement(event) {
  const title = (event.title || "").trim();
  const detail = (event.detail || "").trim();
  if (!title) {
    return detail;
  }
  if (!detail || title.includes(detail)) {
    return title;
  }
  return detail;
}

function formatImprovementPlanCompletedMessage(event) {
  const detail = (event.detail || "").trim();
  const themeMatch = detail.match(/^Theme:\s*(.+?)\.\s*Open the Plans tab/i);
  if (themeMatch && themeMatch[1]) {
    return `I finished a new improvement plan about ${themeMatch[1]}. Open the Plans tab to read it.`;
  }
  return "I finished a new improvement plan. Open the Plans tab to read it.";
}

function formatImplementationAnnouncement(event) {
  const detail = (event.detail || "").trim();
  if (detail) {
    return detail;
  }
  const title = (event.title || "").trim();
  return title;
}

function applyActivityEvent(event) {
  if (
    event.kind === "state" &&
    event.source === "tools.improvement_plan_service.completed"
  ) {
    const message = formatImprovementPlanCompletedMessage(event);
    setAnswer(message, { animate: false, deferClearUntilSpeech: voiceAvailable && !requestInFlight });
    if (voiceAvailable && !requestInFlight) {
      void playVoice(message, { resumeListening: false });
    }
    void loadPlans();
  }

  if (
    event.kind === "log" &&
    event.source === "tools.improvement_plan_implementation.announce" &&
    voiceAvailable &&
    !requestInFlight
  ) {
    const message = formatImplementationAnnouncement(event);
    if (message) {
      setAnswer(message, { animate: false, deferClearUntilSpeech: true });
      void playVoice(message, { resumeListening: false });
    }
    void loadPlans();
  }

  if (event.kind === "log" && event.source === "runtime.task_timer") {
    void syncRuntimeTaskTimer();
    return;
  }

  if (event.kind === "log" && (requestInFlight || currentActivitySnapshot.state === "working")) {
    const progressLine = (event.title || "").trim();
    if (progressLine) {
      const nextState =
        currentActivitySnapshot.state === "error" ? "error" : "working";
      currentActivitySnapshot = {
        ...currentActivitySnapshot,
        state: nextState,
        headline: progressLine,
        detail: (event.detail || "").trim() || progressLine,
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
  if (event.state === "standby" || event.state === "error") {
    syncTaskWaitTimer(null);
  } else {
    void syncRuntimeTaskTimer();
  }
  renderState();
}

async function syncRuntimeTaskTimer() {
  try {
    const snapshot = await loadSnapshot();
    syncTaskWaitTimer(snapshot.task_timer ?? null);
    if (snapshot.task_timer) {
      currentActivitySnapshot = {
        ...currentActivitySnapshot,
        task_timer: snapshot.task_timer,
      };
    }
  } catch (_error) {
    return;
  }
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

async function acknowledgePresenceDismissal() {
  try {
    const response = await fetch("/api/proactive/dismiss", { method: "POST" });
    if (!response.ok) {
      return;
    }
    lastHandledDismissal = null;
  } catch (_error) {
    return;
  }
}

async function syncRuntimeStatus() {
  try {
    const snapshot = await loadSnapshot();
    applyStatusSnapshot(snapshot);
  } catch (error) {
    syncTaskWaitTimer(null);
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
    await refreshStandbyGreeting({ speakOnce: true });
    const commands = await loadToolCommands();
    renderToolCommands(commands);
    await loadPlans();
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
    void loadPlans();
  });
  source.onerror = () => {
    stateLine.textContent = "reconnecting";
    updateEssenceState();
  };
}

