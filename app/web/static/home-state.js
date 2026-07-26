const stateLine = document.getElementById("state-line");
const activityStatus = document.getElementById("activity-status");
const activityStatusText = activityStatus.querySelector(".activity-status-text");
const userSpeech = document.getElementById("user-speech");
const userSpeechText = userSpeech ? userSpeech.querySelector(".user-speech-text") : null;
const activityLog = document.getElementById("activity-log");
const brainsClearButton = document.getElementById("brains-clear");
const voiceStatus = document.getElementById("voice-status");
const replyStatus = document.getElementById("reply-status");
const messageBox = document.getElementById("message");
const sendButton = document.getElementById("send");
const answerOutput = document.getElementById("answer-output");
const voiceAudio = document.getElementById("voice-audio");
const storageLog = document.getElementById("storage-log");
const commandsToggle = document.getElementById("commands-toggle");
const commandsToggleReveal = document.getElementById("commands-toggle-reveal");
const commandsList = document.getElementById("commands-list");
const voiceVolumeInput = document.getElementById("voice-volume");
const voiceVolumeValue = document.getElementById("voice-volume-value");
const keyboardToggle = document.getElementById("keyboard-toggle");
const keyboardPanel = document.getElementById("keyboard-panel");
const viewModal = document.getElementById("view-modal");
const viewModalPanel = document.getElementById("view-modal-panel");
const viewModalTitle = document.getElementById("view-modal-title");
const viewModalClose = document.getElementById("view-modal-close");
const nanoControlsToggle = document.getElementById("nano-controls-toggle");
const viewPanelBrains = document.getElementById("nano-panel-brains");
const viewPanelPlans = document.getElementById("nano-panel-plans");
const viewPanelStorage = document.getElementById("nano-panel-storage");
const viewPanelCommands = document.getElementById("view-panel-commands");
const nanoPanelBrains = viewPanelBrains;
const nanoPanelPlans = viewPanelPlans;
const nanoPanelStorage = viewPanelStorage;
const plansList = document.getElementById("plans-list");
const plansTabCount = document.getElementById("plans-tab-count");
const planReader = document.getElementById("plan-reader");
const planReaderTitle = document.getElementById("plan-reader-title");
const planReaderBody = document.getElementById("plan-reader-body");
const planProcessButton = document.getElementById("plan-process-button");
const planImplementButton = document.getElementById("plan-implement-button");
const planReaderStatus = document.getElementById("plan-reader-status");
const planCopyButton = document.getElementById("plan-copy-button");
const essenceCanvas = document.getElementById("essence-canvas");
const taskWaitTimer = document.getElementById("task-wait-timer");
const taskWaitLabel = taskWaitTimer ? taskWaitTimer.querySelector(".task-wait-label") : null;
const taskWaitClock = taskWaitTimer ? taskWaitTimer.querySelector(".task-wait-clock") : null;
const activeTimersRoot = document.getElementById("active-timers");
const controlsRevealZone = document.getElementById("controls-reveal-zone");
const controlsRevealButton = document.getElementById("controls-reveal");
const commandsRevealZone = document.getElementById("commands-reveal-zone");

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
  task_timer: null,
  active_timers: [],
};
let lastActivityEventId = 0;
let activityLogHiddenBeforeId = 0;
let answerClearTimer = null;
let answerTimeoutTimer = null;
let answerRevealTimer = null;
let answerClearPending = false;
let answerTimeoutPending = false;
let statusClearTimer = null;
let statusClearPending = false;
let statusRevealTimer = null;
let userSpeechFadeTimer = null;
let userSpeechHideTimer = null;
let lastRenderedStatusText = "";
let workingDotsTimer = null;
let currentTaskTimer = null;
let taskWaitClockInterval = null;
let currentActiveTimers = [];
let activeTimersInterval = null;
let savedResponseBeforeWorking = null;
let suppressWorkingResponse = false;
const ANSWER_CLEAR_DELAY_MS = 20000;
const USER_SPEECH_DISPLAY_MS = 5000;
const USER_SPEECH_FADE_MS = 420;
let DEFAULT_NO_ANSWER = "no";
let IDLE_RESPONSE = "How can I help?";
const GREETING_SPOKEN_KEY = "nano.greetingSpoken";
const VOICE_VOLUME_STORAGE_KEY = "nano.voiceVolume";
const DEFAULT_VOICE_VOLUME = 0.8;
let keyboardOpen = false;
let viewSessionActive = false;
let activeView = null;
let viewSessionSource = null;
let viewSessionListening = false;
let activePlanId = null;
let activePlanKind = "drafted";
let speakingActive = false;
let controlsHidden = true;
let waitingForPresence = false;
let waitingForFollowUp = false;
let lastHandledDismissal = null;
let currentStandbyGreeting = "";

let mainEssence = null;
let toolCommands = [];
const activityStates = ["standby", "working", "error"];
let STANDBY_HEADLINE = "I'm in standby.";
let STANDBY_DETAIL_DEFAULT = "Awaiting your input.";
let LISTENING_ACTIVITY_HEADLINE = "Waiting for your input.";
let LISTENING_HEADLINE_DEFAULT = LISTENING_ACTIVITY_HEADLINE;
let WAKE_ARMED_HEADLINE = 'Say "hey nano" when ready.';
let WAKE_ARMED_DETAIL = "Microphone on.";
let COMMAND_LISTEN_HEADLINE = LISTENING_ACTIVITY_HEADLINE;
let VIEW_SESSION_HEADLINE = "Say close to dismiss.";
let WAITING_FOR_ANSWER_HEADLINE = LISTENING_ACTIVITY_HEADLINE;
let FOLLOW_UP_LISTEN_HEADLINE = WAITING_FOR_ANSWER_HEADLINE;
let PRESENCE_LISTEN_HEADLINE = "Are you there?";
let PRESENCE_LISTEN_DETAIL = "Reply yes or no.";
let WORKING_DETAIL_DEFAULT = "Give me a moment.";
let RECEIVED_TITLE = "On it.";
let RECEIVED_DETAIL = "Give me a moment.";

function applyClientCopy(copy) {
  if (!copy || typeof copy !== "object") {
    return;
  }
  if (copy.standbyHeadline) {
    STANDBY_HEADLINE = copy.standbyHeadline;
  }
  if (copy.standbyDetailDefault) {
    STANDBY_DETAIL_DEFAULT = copy.standbyDetailDefault;
  }
  if (copy.listeningActivityHeadline) {
    LISTENING_ACTIVITY_HEADLINE = copy.listeningActivityHeadline;
    LISTENING_HEADLINE_DEFAULT = copy.listeningActivityHeadline;
    COMMAND_LISTEN_HEADLINE = copy.listeningActivityHeadline;
    WAITING_FOR_ANSWER_HEADLINE = copy.listeningActivityHeadline;
    FOLLOW_UP_LISTEN_HEADLINE = copy.listeningActivityHeadline;
  }
  if (copy.wakeArmedHeadline) {
    WAKE_ARMED_HEADLINE = copy.wakeArmedHeadline;
  }
  if (copy.wakeArmedDetail) {
    WAKE_ARMED_DETAIL = copy.wakeArmedDetail;
  }
  if (copy.viewSessionHeadline) {
    VIEW_SESSION_HEADLINE = copy.viewSessionHeadline;
  }
  if (copy.presenceListenHeadline) {
    PRESENCE_LISTEN_HEADLINE = copy.presenceListenHeadline;
  }
  if (copy.presenceListenDetail) {
    PRESENCE_LISTEN_DETAIL = copy.presenceListenDetail;
  }
  if (copy.workingDetailDefault) {
    WORKING_DETAIL_DEFAULT = copy.workingDetailDefault;
  }
  if (copy.receivedTitle) {
    RECEIVED_TITLE = copy.receivedTitle;
  }
  if (copy.receivedDetail) {
    RECEIVED_DETAIL = copy.receivedDetail;
  }
  if (copy.idleResponse) {
    IDLE_RESPONSE = copy.idleResponse;
  }
  if (copy.defaultNoAnswer) {
    DEFAULT_NO_ANSWER = copy.defaultNoAnswer;
  }
}
