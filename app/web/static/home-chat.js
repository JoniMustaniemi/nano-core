async function sendMessage() {
  const message = messageBox.value.trim();
  if (!message) {
    replyStatus.textContent = "Write a message first.";
    return;
  }
  if (tryHandleUiCommand(message)) {
    await completeUiCommand("text");
    messageBox.value = "";
    return;
  }
  if (isBusy()) {
    replyStatus.textContent = "I'm still working. Wait for the current answer.";
    return;
  }
  await submitMessage(message, "text");
  messageBox.value = "";
}

async function sendRecognizedMessage(message) {
  messageBox.value = message;
  if (tryHandleUiCommand(message)) {
    await completeUiCommand("voice");
    messageBox.value = "";
    return;
  }
  await sendMessage();
}

async function acknowledgeRequest(source, commandHint) {
  const commandLabel = (commandHint?.label || "").trim();
  currentActivitySnapshot = {
    ...currentActivitySnapshot,
    state: "working",
    headline: RECEIVED_TITLE,
    detail: commandLabel || RECEIVED_DETAIL,
  };
  suppressWorkingResponse = false;
  renderState();
  if (source === "voice") {
    pauseRecognitionForSpeech();
    if (voiceAvailable) {
      const spokenAck = commandLabel ? `${RECEIVED_TITLE} ${commandLabel}.` : RECEIVED_TITLE;
      await playVoice(spokenAck, { pauseRecognition: true });
    }
  }
}

async function submitDefaultNoAnswer() {
  if (!isWaitingForUserAnswer() || requestInFlight) {
    return;
  }
  clearAnswerTimeoutTimer();
  answerTimeoutPending = false;
  await submitMessage(DEFAULT_NO_ANSWER, "voice");
}

async function submitMessage(message, source, commandHint) {
  clearAnswerTimeoutTimer();
  answerTimeoutPending = false;
  if (tryHandleUiCommand(message)) {
    await completeUiCommand(source);
    return;
  }
  requestInFlight = true;
  await acknowledgeRequest(source, commandHint);
  replyStatus.textContent = source === "voice" ? "Sending voice command..." : "Sending...";
  let answerText = "";
  let shouldSpeak = true;
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
    shouldSpeak = data.speak !== false;
    setAnswer(answerText, { deferClearUntilSpeech: shouldSpeak });
    replyStatus.textContent = "";
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

  if (isWaitingForUserAnswer()) {
    if (shouldSpeak) {
      await playVoice(answerText, { pauseRecognition: true });
    }
    ensureDirectAnswerListening();
    return;
  }

  if (!shouldSpeak) {
    returnToWakeDetection();
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

