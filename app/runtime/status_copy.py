"""Centralized activity status strings for the UI and SSE stream."""

STANDBY_TITLE = "I'm in standby."
STANDBY_DETAIL_DEFAULT = "Awaiting your input."
STANDBY_DETAIL_WAITING = "Awaiting your input."
STANDBY_DETAIL_CONFIRMATION = "Awaiting your confirmation."
STANDBY_DETAIL_PRESENCE = "Awaiting your response."
STANDBY_DETAIL_READY = "Ready for your next task."

BOOT_TITLE = "Booting complete."
BOOT_DETAIL = "I'm ready and awake."
BOOT_SOURCE = "system.boot"

PRESENCE_TITLE = "Are you there?"
PRESENCE_TIMEOUT_TITLE = "I guess not."
PRESENCE_TIMEOUT_DETAIL = "Topic saved for later."
PRESENCE_FOLLOW_UP_DETAIL = "Following up on a saved topic."

THINKING_TITLE = "I'm thinking."
ANSWERING_TITLE = "I'm answering."
REVIEWING_CAPABILITIES_TITLE = "I'm reviewing my capabilities."
INTRODUCING_TITLE = "I'm introducing myself."
PLANNING_ACTION_TITLE = "I'm planning an action."
COULD_NOT_FINISH_TITLE = "I could not finish the task."
NEEDS_DETAIL_TITLE = "I need one detail."
NEEDS_CONFIRMATION_TITLE = "I need confirmation."
PREPARING_CONFIRMATION_TITLE = "I'm preparing confirmation."
SETTING_TIMER_TITLE = "I'm setting a timer."
SAVING_NOTE_TITLE = "I'm saving a note."
SAVED_NOTE_TITLE = "I saved a note."
CHECKED_NOTES_TITLE = "I checked notes."
CANCELLED_NOTE_TITLE = "I cancelled the note."
WIPING_DATABASE_TITLE = "I'm wiping the database."
WIPED_DATABASE_TITLE = "I wiped the database."
CANCELLED_WIPE_TITLE = "I cancelled the wipe."
CANCELLED_UPDATE_TITLE = "I cancelled the update."
PULLING_CHANGES_TITLE = "I'm pulling latest changes."
SWITCHING_BRANCH_TITLE = "I'm switching branches."
PLANNING_SELF_IMPROVE_TITLE = "I'm planning self-improvement."
VERIFYING_SELF_IMPROVE_TITLE = "I'm verifying self-improvement."
PREPARING_PR_TITLE = "I'm preparing a pull request."
COLLECTED_CHANGE_CONTEXT_TITLE = "I collected change context."
VERIFYING_PROJECT_TITLE = "I'm verifying the project."
NAMING_PR_TITLE = "I'm naming the pull request."
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


def running_tool_title(tool_name: str) -> str:
    return f"I'm running {tool_name}."


def ran_tool_title(tool_name: str) -> str:
    return f"I ran {tool_name}."


def could_not_call_tool_title(tool_name: str) -> str:
    return f"I could not call {tool_name}."


def tool_error_title(tool_name: str) -> str:
    return f"I hit an error in {tool_name}."
