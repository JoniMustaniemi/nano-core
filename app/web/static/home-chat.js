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

