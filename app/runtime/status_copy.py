"""Centralized activity status strings for the UI and SSE stream."""

import random

STANDBY_TITLE = "I'm in standby."
STANDBY_DETAIL_DEFAULT = "Awaiting your input."
STANDBY_DETAIL_WAITING = "Awaiting your input."
STANDBY_DETAIL_CONFIRMATION = "Awaiting your confirmation."
STANDBY_DETAIL_PRESENCE = "Awaiting your response."
STANDBY_DETAIL_READY = "Ready for your next task."

BOOT_TITLE = "Booting complete."
BOOT_DETAIL = "I'm ready and awake."
BOOT_SOURCE = "system.boot"

WAKE_ACK_RESPONSES = (
    "I'm listening.",
    "How can I help?",
    "What do you need?",
    "Go ahead.",
    "State your request.",
    "Yes. What is it?",
    "Proceed.",
    "What would you like?",
    "You have my attention.",
    "What's the task?",
    "Say what you need.",
    "I'm ready.",
    "Make it quick.",
    "Your turn.",
    "What can I do for you?",
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
COMPOSING_TITLE = "Pulling it together."
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
SAVING_NOTE_TITLE = "I'm saving a note."
WAITING_NOTE_NAME_DETAIL = "Waiting for the note name."
WAITING_NOTE_CONTENT_DETAIL = "Waiting for the note content."
SAVING_NOTE_DETAIL = "Saving that to memory."
SAVED_NOTE_TITLE = "I saved a note."
SAVED_NOTE_DETAIL = "It's saved."
CHECKED_NOTES_TITLE = "I checked notes."
RETURNED_NOTES_DETAIL = "Returned stored notes."
CANCELLED_NOTE_TITLE = "I cancelled the note."
NO_NOTE_SAVED_DETAIL = "No note was saved."
WIPING_MEMORY_TITLE = "I'm wiping my memory."
WIPED_MEMORY_TITLE = "I wiped my memory."
PREPARING_WIPE_DETAIL = "Preparing confirmation for the destructive request."
WAITING_WIPE_CONFIRMATION_DETAIL = "Waiting for your confirmation before I forget everything."
WIPE_CANCELLED_DETAIL = "Nothing was deleted."
WIPING_MEMORY_DETAIL = (
    "Clearing notes, reminders, conversation, internal notes, and codebase memory."
)
WIPED_MEMORY_DETAIL = (
    "Notes, reminders, conversation history, internal notes, and codebase memory are gone."
)
CANCELLED_WIPE_TITLE = "I cancelled the wipe."
CANCELLED_UPDATE_TITLE = "I cancelled the update."
PREPARING_UPDATE_DETAIL = "Preparing confirmation for pulling latest changes."
WAITING_UPDATE_CONFIRMATION_DETAIL = "Awaiting confirmation before pulling updates."
UPDATE_CANCELLED_DETAIL = "I left everything as it was."
PULLING_CHANGES_TITLE = "I'm pulling latest changes."
PULLING_CHANGES_DETAIL = "Updating from the latest source."
SWITCHING_BRANCH_TITLE = "I'm switching branches."
SWITCHING_BRANCH_DETAIL = "Moving to the right branch before pulling updates."
SELF_IMPROVE_FAILED_TITLE = "I could not improve myself."
SELF_IMPROVE_RELOAD_BLOCKED_ERROR = (
    "Self-improve cannot run while auto-reload is on. "
    "Restart with: python -m app.cli dev --no-reload"
)
PLANNING_SELF_IMPROVE_TITLE = "I'm planning self-improvement."
VERIFYING_SELF_IMPROVE_TITLE = "I'm verifying self-improvement."
VERIFYING_SELF_IMPROVE_DETAIL = "Making sure nothing broke before I ask for a review."
PREPARING_PR_TITLE = "I'm preparing a pull request."
PREPARING_PR_PREFLIGHT_DETAIL = "Running preflight checks."
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
PR_NAMING_FAILED_TITLE = "I could not name the pull request."
VERIFICATION_FAILED_TITLE = "I could not verify the project."
VERIFICATION_PASSED_TITLE = "Verification passed."
SCANNED_SOURCE_FILE_TITLE = "I scanned a source file."
HEALTH_ISSUE_DETECTED_TITLE = "I detected a health issue."
SCHEDULED_REMINDER_TITLE = "I scheduled a reminder."
NOTED_FOR_LATER_TITLE = "I noted something to discuss later."
DISMISSED_FOLLOW_UP_TITLE = "I dismissed a follow-up note."
RESCHEDULED_FOLLOW_UP_TITLE = "I rescheduled a follow-up note."

_TOOL_ACTIVITY_TITLES: dict[str, str] = {
    "add_note": "I'm saving a note.",
    "add_reminder": "I'm scheduling a reminder.",
    "apply_updates_and_restart": "I'm updating myself.",
    "cancel_timers": "I'm cancelling timers.",
    "check_health": "I'm running a health check.",
    "create_pull_request": "I'm opening a pull request.",
    "list_files": "I'm listing files.",
    "list_internal_notes": "I'm reviewing internal notes.",
    "list_notes": "I'm reading notes.",
    "list_reminders": "I'm checking reminders.",
    "list_timers": "I'm checking timers.",
    "propose_self_changes": "I'm improving myself.",
    "read_file": "I'm reading a file.",
    "run_python": "I'm running code.",
    "start_timer": "I'm setting a timer.",
    "write_file": "I'm writing a file.",
}

_TOOL_ACTIVITY_COMPLETED_TITLES: dict[str, str] = {
    "add_note": "I saved a note.",
    "add_reminder": "I scheduled a reminder.",
    "apply_updates_and_restart": "I updated myself.",
    "cancel_timers": "I cancelled timers.",
    "check_health": "I finished the health check.",
    "create_pull_request": "I opened a pull request.",
    "list_files": "I listed files.",
    "list_internal_notes": "I reviewed internal notes.",
    "list_notes": "I read your notes.",
    "list_reminders": "I checked reminders.",
    "list_timers": "I checked timers.",
    "propose_self_changes": "I finished planning improvements.",
    "read_file": "I read a file.",
    "run_python": "I ran code.",
    "start_timer": "I set a timer.",
    "write_file": "I wrote a file.",
}


def running_tool_title(tool_name: str) -> str:
    return _TOOL_ACTIVITY_TITLES.get(tool_name, "I'm working on something.")


def ran_tool_title(tool_name: str) -> str:
    return _TOOL_ACTIVITY_COMPLETED_TITLES.get(tool_name, "I finished that.")


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
            "timer": (SETTING_TIMER_TITLE, SETTING_TIMER_DETAIL),
            "note": (SAVING_NOTE_TITLE, SAVING_NOTE_DETAIL),
            "self_update": (PULLING_CHANGES_TITLE, PREPARING_UPDATE_DETAIL),
        }
        return interaction_titles.get(interaction or "", (RECEIVED_TITLE, RECEIVED_DETAIL))
    return RECEIVED_TITLE, RECEIVED_DETAIL
