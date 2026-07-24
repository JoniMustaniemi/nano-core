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
    setControlsHidden(false);
  });
}
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && controlsHidden) {
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
  if (miniEssence) {
    miniEssence.destroy();
  }
});

window.addEventListener("load", () => {
  requestAnimationFrame(() => {
    initEssence();
    void initVoiceVolumeControl();
    setAnswer("", { animate: false });
    setVoiceStatus("Voice on standby.");
    updateListenButton();
    bootstrap();
  });
});
