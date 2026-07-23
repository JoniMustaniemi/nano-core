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
  const tabs = {
    brains: nanoTabBrains,
    plans: nanoTabPlans,
    storage: nanoTabStorage,
  };
  const panels = {
    brains: nanoPanelBrains,
    plans: nanoPanelPlans,
    storage: nanoPanelStorage,
  };
  for (const [name, button] of Object.entries(tabs)) {
    const isActive = name === tab;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
    panels[name].classList.toggle("active", isActive);
    panels[name].hidden = !isActive;
  }
  if (tab === "plans") {
    void loadPlans();
  }
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

