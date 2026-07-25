const VIEW_TITLES = {
  brains: "Brains",
  plans: "Plans",
  storage: "Stored data",
  commands: "Commands",
};

const VIEW_OPEN_ACK = {
  brains: "Opening Brains.",
  plans: "Opening Plans.",
  storage: "Opening stored data.",
  commands: "Opening commands.",
};

function matchViewCloseKeyword(message) {
  return matchesCloseCommand(message);
}

function isViewSessionActive() {
  return viewSessionActive;
}

function getActiveViewSession() {
  return viewSessionActive ? activeView : null;
}

function isViewSessionVoiceGated() {
  return viewSessionActive;
}

function showViewPanel(view) {
  const panels = {
    brains: viewPanelBrains,
    plans: viewPanelPlans,
    storage: viewPanelStorage,
    commands: viewPanelCommands,
  };
  for (const [name, panel] of Object.entries(panels)) {
    if (!panel) {
      continue;
    }
    const isActive = name === view;
    panel.hidden = !isActive;
    panel.classList.toggle("active", isActive);
  }
}

async function loadViewData(view) {
  if (view === "plans") {
    closePlanReader();
    await loadPlans();
  } else if (view === "storage") {
    await refreshStorage();
  } else if (view === "commands") {
    if (!commandsList.querySelector(".command-button")) {
      await loadAndRenderToolCommands();
    }
    expandCommandDropdowns();
    applyVoiceVolume();
  }
}

function setViewModalExpanded(expanded) {
  const value = expanded ? "true" : "false";
  if (commandsToggle) {
    commandsToggle.setAttribute("aria-expanded", value);
  }
  if (commandsToggleReveal) {
    commandsToggleReveal.setAttribute("aria-expanded", value);
  }
  if (nanoControlsToggle) {
    nanoControlsToggle.setAttribute(
      "aria-expanded",
      expanded && activeView !== "commands" ? "true" : "false"
    );
  }
}

function ensureViewSessionListening() {
  viewSessionListening = true;
  listeningForCommand = false;
  waitingForFollowUp = false;
  setVoiceStatus("Say close to dismiss.");
  if (microphoneReady) {
    startVoiceListening("resume", true);
  }
  renderState();
}

function resetViewSessionListening() {
  viewSessionListening = false;
}

function openViewModalShell(view) {
  if (!viewModal || !viewModalTitle) {
    return;
  }
  viewModalTitle.textContent = VIEW_TITLES[view] || "View";
  showViewPanel(view);
  viewModal.classList.add("open");
  viewModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("view-modal-open");
  setViewModalExpanded(true);
  if (viewModalClose) {
    viewModalClose.focus();
  }
}

function closeViewModalShell() {
  if (!viewModal) {
    return;
  }
  viewModal.classList.remove("open");
  viewModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("view-modal-open");
  setViewModalExpanded(false);
}

async function openViewSession(view, { source = "ui" } = {}) {
  if (getDisplayState() === "working") {
    return false;
  }
  if (!VIEW_TITLES[view]) {
    return false;
  }
  revealControlsForUiCommand();
  if (viewSessionActive) {
    closeViewSession({ reason: "switch", restoreWake: false });
  }
  activeView = view;
  viewSessionActive = true;
  viewSessionSource = source;
  openViewModalShell(view);
  await loadViewData(view);
  if (source === "voice" || microphoneReady) {
    ensureViewSessionListening();
  }
  return true;
}

function closeViewSession({ reason = "ui", restoreWake = true } = {}) {
  if (!viewSessionActive) {
    closeViewModalShell();
    resetViewSessionListening();
    return;
  }
  viewSessionActive = false;
  activeView = null;
  viewSessionSource = null;
  resetViewSessionListening();
  closeViewModalShell();
  controlsHidden = true;
  closeKeyboardPanel();
  applyControlsVisibility();
  if (restoreWake) {
    returnToWakeDetection();
  }
  renderState();
}

function handleViewSessionTranscript(text) {
  if (!isViewSessionActive()) {
    return false;
  }
  if (!matchViewCloseKeyword(text)) {
    return false;
  }
  if (typeof isPlanReaderOpen === "function" && isPlanReaderOpen()) {
    closePlanReader();
    ensureViewSessionListening();
    setVoiceStatus("Plan closed. Say close to dismiss.");
    return true;
  }
  closeViewSession({ reason: "voice" });
  return true;
}

function getViewOpenAck(view) {
  return VIEW_OPEN_ACK[view] || "Opening.";
}
