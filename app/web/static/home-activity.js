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
  if (snapshot.copy) {
    applyClientCopy(snapshot.copy);
  }
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
    active_timers: Array.isArray(snapshot.active_timers) ? snapshot.active_timers : [],
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
  syncActiveTimers(snapshot.active_timers ?? []);
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

function getActiveTimerRemainingSeconds(timer) {
  if (!timer || !timer.due_at) {
    return 0;
  }
  const dueAt = Date.parse(timer.due_at);
  if (Number.isNaN(dueAt)) {
    return 0;
  }
  return Math.max(0, Math.floor((dueAt - Date.now()) / 1000));
}

function getActiveTimerElapsedSeconds(timer) {
  if (!timer || !timer.started_at) {
    return 0;
  }
  const startedAt = Date.parse(timer.started_at);
  if (Number.isNaN(startedAt)) {
    return 0;
  }
  return Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
}

function getActiveTimerDisplaySeconds(timer) {
  if (timer && timer.kind === "stopwatch") {
    return getActiveTimerElapsedSeconds(timer);
  }
  return getActiveTimerRemainingSeconds(timer);
}

function renderActiveTimerItem(timer) {
  const item = document.createElement("div");
  item.className = "active-timer-item";

  const label = (timer.label || "").trim();
  const defaultLabel = timer.kind === "stopwatch" ? "Stopwatch" : "Timer";
  if (label && label !== defaultLabel) {
    const labelEl = document.createElement("span");
    labelEl.className = "active-timer-label";
    labelEl.textContent = label;
    item.append(labelEl);
  }

  const clock = document.createElement("span");
  clock.className = "active-timer-clock";
  clock.textContent = formatTaskWaitClock(getActiveTimerDisplaySeconds(timer));
  if (label && label !== defaultLabel) {
    clock.setAttribute("aria-label", `${label} ${clock.textContent}`);
  } else {
    clock.setAttribute("aria-label", clock.textContent);
  }

  item.append(clock);
  return item;
}

function renderActiveTimersGrid(timers, { singleTypeMode = false } = {}) {
  const grid = document.createElement("div");
  grid.className = "active-timers-grid";
  if (singleTypeMode) {
    grid.classList.add("active-timers-grid--single-type");
  }
  for (const timer of timers) {
    grid.appendChild(renderActiveTimerItem(timer));
  }
  return grid;
}

function renderActiveTimersSection(title, timers) {
  const section = document.createElement("section");
  section.className = "active-timers-section";

  const heading = document.createElement("h2");
  heading.className = "active-timers-section-title";
  heading.textContent = title;

  section.append(heading, renderActiveTimersGrid(timers));
  return section;
}

function renderActiveTimers(timers) {
  if (!activeTimersRoot) {
    return;
  }
  const items = Array.isArray(timers) ? timers : [];
  if (!items.length) {
    activeTimersRoot.hidden = true;
    activeTimersRoot.replaceChildren();
    return;
  }
  activeTimersRoot.hidden = false;
  activeTimersRoot.replaceChildren();

  const countdownTimers = items.filter((timer) => timer.kind !== "stopwatch");
  const stopwatches = items.filter((timer) => timer.kind === "stopwatch");
  const showSections = countdownTimers.length > 0 && stopwatches.length > 0;

  if (showSections) {
    if (countdownTimers.length) {
      activeTimersRoot.appendChild(renderActiveTimersSection("Timers", countdownTimers));
    }
    if (stopwatches.length) {
      activeTimersRoot.appendChild(renderActiveTimersSection("Stopwatches", stopwatches));
    }
    return;
  }

  activeTimersRoot.appendChild(
    renderActiveTimersGrid(items, { singleTypeMode: true }),
  );
}

function clearActiveTimersInterval() {
  if (activeTimersInterval !== null) {
    window.clearInterval(activeTimersInterval);
    activeTimersInterval = null;
  }
}

function syncActiveTimers(timers) {
  currentActiveTimers = Array.isArray(timers) ? timers : [];
  clearActiveTimersInterval();
  renderActiveTimers(currentActiveTimers);
  if (!currentActiveTimers.length) {
    return;
  }
  activeTimersInterval = window.setInterval(() => {
    renderActiveTimers(currentActiveTimers);
  }, 1000);
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

function formatImplementationFailureFromState(event) {
  const title = (event.title || "").trim();
  const detail = (event.detail || "").trim();
  if (detail && detail !== title && !title.includes(detail)) {
    return detail;
  }
  return title;
}

function formatImplementationAnnouncement(event) {
  const detail = (event.detail || "").trim();
  if (detail) {
    return detail;
  }
  const title = (event.title || "").trim();
  return title;
}

let lastVoiceAnnouncement = "";
let selfImprovementRunSettled = false;

function normalizeVoiceAnnouncement(message) {
  const skip = new Set(["the", "a"]);
  const words = (message || "").trim().toLowerCase().replace(/\.$/, "").split(/\s+/).filter(Boolean);
  return words.filter((word) => !skip.has(word)).join(" ");
}

function isImplementationTerminalMessage(message) {
  const lowered = (message || "").toLowerCase();
  return (
    lowered.includes("implemented the improvement plan") ||
    lowered.includes("declined to commit") ||
    lowered.includes("tests failed") ||
    lowered.includes("could not implement")
  );
}

function releaseSelfImprovementWorkingMode({ headline, detail, state = "standby" } = {}) {
  const nextState = activityStates.includes(state) ? state : "standby";
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: nextState,
    headline: headline || STANDBY_HEADLINE,
    detail: detail ?? STANDBY_DETAIL_DEFAULT,
    task_timer: null,
  };
  syncTaskWaitTimer(null);
  suppressWorkingResponse = false;
  selfImprovementRunSettled = true;
  renderState();
}

function speakVoiceAnnouncement(message) {
  const cleaned = (message || "").trim();
  if (!cleaned || !voiceAvailable) {
    return;
  }
  const normalized = normalizeVoiceAnnouncement(cleaned);
  if (normalized === normalizeVoiceAnnouncement(lastVoiceAnnouncement)) {
    return;
  }
  lastVoiceAnnouncement = cleaned;
  if (getDisplayState() !== "working" && !requestInFlight) {
    setAnswer(cleaned, { animate: false, deferClearUntilSpeech: true });
  }
  void playVoice(cleaned, { pauseRecognition: true, resumeListening: false });
}

function applyActivityEvent(event) {
  if (
    event.kind === "state" &&
    event.state === "working" &&
    (event.source === "tools.improvement_plan_service" ||
      event.source === "tools.improvement_plan_implementation")
  ) {
    selfImprovementRunSettled = false;
  }

  if (
    event.kind === "state" &&
    event.source === "tools.improvement_plan_service.completed.silent"
  ) {
    releaseSelfImprovementWorkingMode({
      headline: event.title,
      detail: event.detail,
    });
    void loadPlans();
    return;
  }

  if (
    event.kind === "state" &&
    event.source === "tools.improvement_plan_service.completed"
  ) {
    const message = formatImprovementPlanCompletedMessage(event);
    setAnswer(message, { animate: false, deferClearUntilSpeech: voiceAvailable && !requestInFlight });
    if (voiceAvailable && !requestInFlight) {
      void playVoice(message, { resumeListening: false });
    }
    releaseSelfImprovementWorkingMode({
      headline: event.title,
      detail: event.detail,
    });
    void loadPlans();
    return;
  }

  if (
    event.kind === "log" &&
    event.source === "runtime.voice.announce"
  ) {
    const message = formatImplementationAnnouncement(event);
    if (message && !message.includes("http://") && !message.includes("https://")) {
      if (message.toLowerCase().includes("implemented the improvement plan")) {
        lastVoiceAnnouncement = "";
      }
      speakVoiceAnnouncement(message);
      if (isImplementationTerminalMessage(message)) {
        releaseSelfImprovementWorkingMode({
          headline: message,
          detail: message,
        });
      }
    }
    void loadPlans();
    return;
  }

  if (
    event.kind === "state" &&
    event.source === "tools.improvement_plan_implementation" &&
    (event.state === "standby" || event.state === "error")
  ) {
    releaseSelfImprovementWorkingMode({
      headline: event.title || currentActivitySnapshot.headline,
      detail: event.detail ?? currentActivitySnapshot.detail,
      state: event.state,
    });
    void loadPlans();
    return;
  }

  if (event.kind === "log" && event.source === "runtime.task_timer") {
    void syncRuntimeTaskTimer();
    return;
  }

  if (
    event.kind === "log" &&
    (event.source === "assistant.flows.timer" || event.source === "scheduler.timers")
  ) {
    void syncRuntimeActiveTimers();
    return;
  }

  if (event.kind === "log" && currentActivitySnapshot.state === "working") {
    if (selfImprovementRunSettled && !requestInFlight) {
      return;
    }
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

  if (
    event.source === "tools.pr_service" &&
    (event.state === "standby" || event.state === "error")
  ) {
    syncTaskWaitTimer(null);
    suppressWorkingResponse = false;
    selfImprovementRunSettled = true;
  }

  if (
    selfImprovementRunSettled &&
    event.state === "working" &&
    (event.source === "tools.pr_service" ||
      event.source === "tools.improvement_plan_implementation" ||
      event.source === "runtime.long_task_progress")
  ) {
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

async function syncRuntimeActiveTimers() {
  try {
    const snapshot = await loadSnapshot();
    syncActiveTimers(snapshot.active_timers ?? []);
    currentActivitySnapshot = {
      ...currentActivitySnapshot,
      active_timers: Array.isArray(snapshot.active_timers) ? snapshot.active_timers : [],
    };
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
    syncActiveTimers([]);
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
    await loadAndRenderToolCommands();
    void refreshStandbyGreeting({ speakOnce: true });
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
  const source = new EventSource(`/api/events?since=${lastEventId}`);
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

