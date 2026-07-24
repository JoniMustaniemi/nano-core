sendButton.addEventListener("click", sendMessage);
commandsToggle.addEventListener("click", openCommandsDrawer);
if (commandsToggleReveal) {
  commandsToggleReveal.addEventListener("click", openCommandsDrawer);
}
commandsClose.addEventListener("click", closeCommandsDrawer);
commandsBackdrop.addEventListener("click", closeCommandsDrawer);
commandsPanel.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeCommandsDrawer();
  }
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
nanoTabPlans.addEventListener("click", () => setNanoTab("plans"));
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
if (controlsRevealButton) {
  controlsRevealButton.addEventListener("click", () => {
    if (getDisplayState() === "working") {
      return;
    }
    setControlsHidden(false);
  });
}
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && controlsHidden && getDisplayState() !== "working") {
    setControlsHidden(false);
  }
});
window.addEventListener("pointerdown", maybeStartListeningAfterGesture, { passive: true });
window.addEventListener("keydown", maybeStartListeningAfterGesture);
window.addEventListener("beforeunload", () => {
  if (microphoneStream) {
    for (const track of microphoneStream.getTracks()) {
      track.stop();
    }
  }
  if (mainEssence) {
    mainEssence.destroy();
  }
});

window.addEventListener("load", () => {
  requestAnimationFrame(() => {
    initEssence();
    applyControlsVisibility();
    void initVoiceVolumeControl();
    restoreBaseAnswer();
    setVoiceStatus("Voice on standby.");
    syncVoiceListeningState();
    bootstrap();
  });
});
