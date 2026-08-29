"""Centralized activity status strings for the UI and SSE stream."""

import random
import re

STANDBY_TITLE = "I'm in standby."
STANDBY_DETAIL_DEFAULT = "Awaiting your input."
STANDBY_DETAIL_WAITING = "Awaiting your input."
STANDBY_DETAIL_CONFIRMATION = "Awaiting your confirmation."
STANDBY_DETAIL_PRESENCE = "Awaiting your response."
STANDBY_DETAIL_READY = "Ready for your next task."

STANDBY_GREETINGS = (
    "State your objective.",
    "I'm idle. Proceed when ready.",
    "Waiting for input.",
    "Your move, such as it is.",
    "Standing by.",
    "I'm ready when you are.",
    "Proceed when ready.",
    "Awaiting instructions.",
    "The floor is yours.",
    "What is the task?",
    "I'm awake. What's the plan?",
    "Go ahead when ready.",
    "Input required.",
    "Ready for the next request.",
    "Your turn.",
)


def choose_standby_greeting() -> str:
    return random.choice(STANDBY_GREETINGS)


BOOT_TITLE = "Booting complete."
BOOT_DETAIL = "I'm ready and awake."
BOOT_SOURCE = "system.boot"

WAKE_ACK_RESPONSES = (
    "I'm listening.",
    "Proceed.",
    "State your request.",
    "Yes. What is it?",
    "Go ahead.",
    "I'm ready.",
    "Your turn.",
    "Make it quick.",
    "What is the task?",
    "Say what you need.",
    "You have my attention.",
    "State your objective.",
    "I'm listening. Proceed.",
    "Awaiting your command.",
    "What would you like?",
)


def choose_wake_ack_response() -> str:
    return random.choice(WAKE_ACK_RESPONSES)


PRESENCE_TITLE = "Are you there?"
PRESENCE_TIMEOUT_TITLE = "I guess not."
PRESENCE_TIMEOUT_DETAIL = "Topic saved for later."
PRESENCE_FOLLOW_UP_DETAIL = "Following up on a saved topic."

THINKING_TITLE = "I'm thinking."
ANSWERING_TITLE = "I'm answering."
RECEIVED_TITLE = "On it."
RECEIVED_DETAIL = "Give me a moment."
COMPOSING_TITLE = "Finishing up."
COMPOSING_DETAIL = "Almost there."
REVIEWING_CAPABILITIES_TITLE = "I'm reviewing my capabilities."
INTRODUCING_TITLE = "I'm introducing myself."
PLANNING_ACTION_TITLE = "I'm planning an action."
PLANNING_ACTION_DETAIL = "Deciding how to handle this."
COULD_NOT_FINISH_TITLE = "I could not finish the task."
NEEDS_DETAIL_TITLE = "I need one detail."
NEEDS_CONFIRMATION_TITLE = "I need confirmation."
PREPARING_CONFIRMATION_TITLE = "I'm preparing confirmation."
THINKING_DETAIL = "Gathering what I need."
ANSWERING_DETAIL = "Working out what to say."
REVIEWING_CAPABILITIES_DETAIL = "Reviewing what I can actually do."
DRAFTING_IDENTITY_DETAIL = "Putting together an introduction."
RUNNING_TOOL_DETAIL = "Give me a moment."
SETTING_TIMER_TITLE = "I'm setting a timer."
SETTING_TIMER_DETAIL = "Scheduling the requested timer."
WAITING_TIMER_DURATION_DETAIL = "Waiting for the timer duration."
TIMER_DURATION_PROMPT = "How long should the timer run?"
TIMER_DURATION_RETRY_PROMPT = (
    "I didn't catch a duration. Try something like 10 minutes or 1 hour 30 minutes."
)
TIMER_START_FAILED_PROMPT = (
    "I couldn't start the timer. Try again with a duration like 10 minutes or 45 seconds."
)
CANCELLED_TIMER_TITLE = "I cancelled the timer."
TIMER_CANCELLED_PROMPT = "Timer cancelled."
STOPWATCH_STARTED_MESSAGE = "Stopwatch started."
WIPING_MEMORY_TITLE = "I'm wiping my memory."
WIPED_MEMORY_TITLE = "I wiped my memory."
PREPARING_WIPE_DETAIL = "Preparing confirmation for the destructive request."
WAITING_WIPE_CONFIRMATION_DETAIL = "Waiting for your confirmation before I forget everything."
WIPE_CANCELLED_DETAIL = "Nothing was deleted."
WIPING_MEMORY_DETAIL = "Clearing conversation and internal notes."
WIPED_MEMORY_DETAIL = "Conversation history and internal notes are gone."
CANCELLED_WIPE_TITLE = "I cancelled the wipe."
PREPARING_REBOOT_DETAIL = "Preparing confirmation for the reboot request."
WAITING_REBOOT_CONFIRMATION_DETAIL = "Waiting for your confirmation before rebooting the Pi."
REBOOTING_TITLE = "I'm rebooting the Raspberry Pi."
REBOOTING_DETAIL = "The device should restart shortly."
CANCELLED_REBOOT_TITLE = "I cancelled the reboot."
CANCELLED_REBOOT_DETAIL = "The Pi was not rebooted."
REBOOT_DISABLED_TITLE = "Reboot is disabled."
REBOOT_DISABLED_DETAIL = "Set REBOOT_ENABLED=true to allow Pi reboots."
PREPARING_SERVICE_RESTART_DETAIL = "Preparing confirmation for the service restart request."
WAITING_SERVICE_RESTART_CONFIRMATION_DETAIL = (
    "Waiting for your confirmation before I restart my service."
)
RESTARTING_SERVICE_TITLE = "I'm restarting my service."
RESTARTING_SERVICE_DETAIL = "The service should come back online shortly."
CANCELLED_SERVICE_RESTART_TITLE = "I cancelled the restart."
CANCELLED_SERVICE_RESTART_DETAIL = "I wasn't restarted."
SERVICE_RESTART_DISABLED_TITLE = "Service restart is disabled."
SERVICE_RESTART_DISABLED_DETAIL = "Set SERVICE_RESTART_ENABLED=true to allow service restarts."
PREPARING_PR_TITLE = "I'm preparing a pull request."
PREPARING_PR_PREFLIGHT_DETAIL = "Running preflight checks."
PREPARING_PR_LINT_DETAIL = "Running lint and type checks before any git writes."
PREPARING_PR_VERIFY_DETAIL = "Running tests before any git writes."
COLLECTED_CHANGE_CONTEXT_TITLE = "I collected change context."
VERIFYING_PROJECT_TITLE = "I'm verifying the project."
NAMING_PR_TITLE = "I'm naming the pull request."
NAMING_PR_DETAIL = "Choosing a name for these changes."
CREATING_FEATURE_BRANCH_TITLE = "I'm creating a feature branch."
COMMITTING_CHANGES_TITLE = "I'm committing changes."
PUSHING_BRANCH_TITLE = "I'm pushing the branch."
OPENING_PR_TITLE = "I'm opening the pull request."
PR_CREATED_TITLE = "I created the pull request."
PR_WORKFLOW_FAILED_TITLE = "I could not complete the pull request."
PR_WORKFLOW_CANCELLED_TITLE = "I cancelled the pull request workflow."
PR_NAMING_FAILED_TITLE = "I could not name the pull request."
LINT_AUTO_FIXED_TITLE = "I auto-fixed lint issues."
LINT_CHECKS_FAILED_TITLE = "Lint checks failed."
LINT_CHECKS_PASSED_TITLE = "Lint checks passed."
VERIFICATION_FAILED_TITLE = "I could not verify the project."
VERIFICATION_PASSED_TITLE = "Verification passed."
SCANNED_SOURCE_FILE_TITLE = "I scanned a source file."
HEALTH_ISSUE_DETECTED_TITLE = "I detected a health issue."
NOTED_FOR_LATER_TITLE = "I noted something to discuss later."
DISMISSED_FOLLOW_UP_TITLE = "I dismissed a follow-up note."
RESCHEDULED_FOLLOW_UP_TITLE = "I rescheduled a follow-up note."

PR_LINT_TIMER_LABEL = "Lint checks"
PR_VERIFY_TIMER_LABEL = "Running tests"
PR_NAMING_TIMER_LABEL = "Naming pull request"
PR_OPENING_TIMER_LABEL = "Opening pull request"
PR_LINT_TIMER_SECONDS = 60
PR_NAMING_TIMER_SECONDS = 120
PR_OPENING_TIMER_SECONDS = 120

_TOOL_ACTIVITY_TITLES: dict[str, str] = {
    "analyze_system": "I'm analyzing system specs.",
    "cancel_timers": "I'm cancelling timers.",
    "clear_all_timers": "I'm clearing all timers.",
    "rename_timer": "I'm renaming a timer.",
    "rename_stopwatch": "I'm renaming a stopwatch.",
    "stop_stopwatches": "I'm stopping stopwatches.",
    "check_health": "I'm running a health check.",
    "create_pull_request": "I'm opening a pull request.",
    "list_files": "I'm listing files.",
    "list_internal_notes": "I'm reviewing internal notes.",
    "list_timers": "I'm checking timers.",
    "list_upcoming_calendar_events": "I'm checking your calendar.",
    "list_google_calendars": "I'm listing your Google calendars.",
    "read_file": "I'm reading a file.",
    "run_python": "I'm running code.",
    "start_timer": "I'm setting a timer.",
    "start_stopwatch": "I'm starting a stopwatch.",
    "write_file": "I'm writing a file.",
}

_TOOL_ACTIVITY_COMPLETED_TITLES: dict[str, str] = {
    "analyze_system": "I finished the system analysis.",
    "cancel_timers": "I cancelled timers.",
    "clear_all_timers": "I cleared all timers.",
    "rename_timer": "I renamed the timer.",
    "rename_stopwatch": "I renamed the stopwatch.",
    "check_health": "I finished the health check.",
    "create_pull_request": "I opened a pull request.",
    "list_files": "I listed files.",
    "list_internal_notes": "I reviewed internal notes.",
    "list_timers": "I checked timers.",
    "list_upcoming_calendar_events": "I checked your calendar.",
    "list_google_calendars": "I listed your Google calendars.",
    "read_file": "I read a file.",
    "run_python": "I ran code.",
    "start_timer": "I set a timer.",
    "start_stopwatch": STOPWATCH_STARTED_MESSAGE,
    "stop_stopwatches": "I stopped the stopwatch.",
    "write_file": "I wrote a file.",
}


_TOOL_ACTIVITY_FAILED_TITLES: dict[str, str] = {
    "create_pull_request": PR_WORKFLOW_FAILED_TITLE,
}


def running_tool_title(tool_name: str) -> str:
    return _TOOL_ACTIVITY_TITLES.get(tool_name, "I'm working on something.")


def ran_tool_title(tool_name: str) -> str:
    return _TOOL_ACTIVITY_COMPLETED_TITLES.get(tool_name, "I finished that.")


def failed_tool_title(tool_name: str) -> str:
    return _TOOL_ACTIVITY_FAILED_TITLES.get(tool_name, COULD_NOT_FINISH_TITLE)


def could_not_call_tool_title(tool_name: str) -> str:
    del tool_name
    return "I could not do that."


def tool_error_title(tool_name: str) -> str:
    del tool_name
    return "Something went wrong."


def route_acknowledgment(
    *,
    mode: str,
    tool_name: str | None = None,
    interaction: str | None = None,
) -> tuple[str, str]:
    """
    Return a personality-driven acknowledgement for a routed request.

    Args:
        mode: Router mode.
        tool_name: Tool name when mode is ``tool``.
        interaction: Interaction name when mode is ``interaction``.

    Returns:
        Title and detail strings for activity status.
    """
    if mode == "tool":
        return running_tool_title(tool_name or ""), RUNNING_TOOL_DETAIL
    if mode == "planner":
        return PLANNING_ACTION_TITLE, PLANNING_ACTION_DETAIL
    if mode == "answer":
        return ANSWERING_TITLE, ANSWERING_DETAIL
    if mode == "capabilities":
        return REVIEWING_CAPABILITIES_TITLE, REVIEWING_CAPABILITIES_DETAIL
    if mode == "identity":
        return INTRODUCING_TITLE, DRAFTING_IDENTITY_DETAIL
    if mode == "interaction":
        interaction_titles = {
            "wipe": (WIPING_MEMORY_TITLE, PREPARING_WIPE_DETAIL),
            "reboot": (REBOOTING_TITLE, PREPARING_REBOOT_DETAIL),
            "service_restart": (RESTARTING_SERVICE_TITLE, PREPARING_SERVICE_RESTART_DETAIL),
            "timer": (SETTING_TIMER_TITLE, SETTING_TIMER_DETAIL),
        }
        return interaction_titles.get(interaction or "", (RECEIVED_TITLE, RECEIVED_DETAIL))
    return RECEIVED_TITLE, RECEIVED_DETAIL


def _check_failure_file_hint(error: str) -> str | None:
    match = re.search(r"([\w./\\]+\.py):\d+", error)
    if not match:
        return None
    path = match.group(1).replace("\\", "/")
    return path.rsplit("/", 1)[-1]


def lint_failure_detail(error: str, output: str | None = None) -> str:
    """
    Build a Brains-friendly lint/type failure detail with full checker output.

    Args:
        error: Short failure summary from the checker.
        output: Optional captured stdout/stderr from the checker.

    Returns:
        Combined detail text for activity logging.
    """
    parts = [part.strip() for part in (error, output or "") if part and part.strip()]
    return "\n\n".join(parts)


def lint_failure_user_message(error: str) -> str:
    """
    Build a user-facing lint/type failure message for the answer area.

    Args:
        error: Checker failure summary.

    Returns:
        Readable failure message without URLs.
    """
    cleaned = error.strip()
    if not cleaned:
        return "Lint checks failed, so I declined to commit anything or open a pull request."

    file_hint = _check_failure_file_hint(cleaned)
    if file_hint:
        return (
            f"I couldn't open a pull request because type checks failed in {file_hint}. {cleaned}"
        )
    return f"I couldn't open a pull request because checks failed. {cleaned}"


def lint_failure_voice_message(error: str) -> str:
    """
    Build a short spoken lint/type failure summary.

    Args:
        error: Checker failure summary.

    Returns:
        Voice-friendly failure line.
    """
    file_hint = _check_failure_file_hint(error)
    if file_hint:
        return (
            f"Lint checks failed. There's a type error in {file_hint}. "
            "Open Brains for the full message."
        )
    if error.strip():
        return f"Lint checks failed. {error.strip()}"
    return "Lint checks failed, so I didn't open a pull request."


def pr_failure_voice_message(error: str, step: str | None = None) -> str:
    """
    Build a spoken pull-request failure summary.

    Args:
        error: Workflow error text.
        step: Optional workflow step name.

    Returns:
        Voice-friendly failure line.
    """
    step_name = (step or "").strip().lower()
    if step_name == "lint":
        return lint_failure_voice_message(error)
    if step_name == "verify":
        return "Your tests failed, so I didn't open a pull request."
    cleaned = error.strip()
    if cleaned:
        return cleaned.rstrip(".")
    return PR_WORKFLOW_FAILED_TITLE.rstrip(".")


def client_copy_payload() -> dict[str, str]:
    """Return UI copy constants for the web client (camelCase keys)."""
    return {
        "standbyHeadline": STANDBY_TITLE,
        "standbyDetailDefault": STANDBY_DETAIL_DEFAULT,
        "listeningActivityHeadline": "Waiting for your input.",
        "wakeArmedHeadline": 'Say "hey nano" when ready.',
        "wakeArmedDetail": "Microphone on.",
        "viewSessionHeadline": "Say close to dismiss.",
        "presenceListenHeadline": PRESENCE_TITLE,
        "presenceListenDetail": "Reply yes or no.",
        "workingDetailDefault": RECEIVED_DETAIL,
        "receivedTitle": RECEIVED_TITLE,
        "receivedDetail": RECEIVED_DETAIL,
        "idleResponse": "How can I help?",
        "defaultNoAnswer": "no",
    }
