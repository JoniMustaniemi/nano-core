"""Centralized activity status strings for the UI and SSE stream."""

import random

STANDBY_TITLE = "I'm in standby."
STANDBY_DETAIL_DEFAULT = "Awaiting your input."
STANDBY_DETAIL_WAITING = "Awaiting your input."
STANDBY_DETAIL_CONFIRMATION = "Awaiting your confirmation."
STANDBY_DETAIL_PRESENCE = "Awaiting your response."
STANDBY_DETAIL_READY = "Ready for your next task."

STANDBY_GREETINGS = (
    "What can I do for you today?",
    "Ready when you are.",
    "What's on your mind?",
    "I'm here if you need something.",
    "Say the word.",
    "Standing by.",
    "What would you like?",
    "Your move.",
    "I'm awake. What's the plan?",
    "Need anything?",
    "At your service.",
    "What's next?",
    "Go ahead — I'm ready.",
    "Anything I can help with?",
    "The floor is yours.",
)


def choose_standby_greeting() -> str:
    return random.choice(STANDBY_GREETINGS)


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
TIMER_DURATION_PROMPT = "How long should the timer run? Try 30 seconds or 5 minutes."
TIMER_DURATION_RETRY_PROMPT = "I didn't catch a duration. Try 30 seconds or 5 minutes."
TIMER_START_FAILED_PROMPT = (
    "I couldn't start the timer. Try again with a duration like 30 seconds or 5 minutes."
)
CANCELLED_TIMER_TITLE = "I cancelled the timer."
TIMER_CANCELLED_PROMPT = "Timer cancelled."
WIPING_MEMORY_TITLE = "I'm wiping my memory."
WIPED_MEMORY_TITLE = "I wiped my memory."
PREPARING_WIPE_DETAIL = "Preparing confirmation for the destructive request."
WAITING_WIPE_CONFIRMATION_DETAIL = "Waiting for your confirmation before I forget everything."
WIPE_CANCELLED_DETAIL = "Nothing was deleted."
WIPING_MEMORY_DETAIL = (
    "Clearing conversation, internal notes, improvement plans, and codebase memory."
)
WIPED_MEMORY_DETAIL = (
    "Conversation history, internal notes, improvement plans, and codebase memory are gone."
)
CANCELLED_WIPE_TITLE = "I cancelled the wipe."
DRAFTING_IMPROVEMENT_PLAN_TITLE = "I'm drafting an improvement plan."
DRAFTING_IMPROVEMENT_PLAN_DETAIL = "Reviewing code and writing a readable plan."
IMPROVEMENT_PLAN_FAILED_TITLE = "I could not draft an improvement plan."
PREPARING_PR_TITLE = "I'm preparing a pull request."
PREPARING_PR_PREFLIGHT_DETAIL = "Running preflight checks."
PREPARING_PR_LINT_DETAIL = "Running lint checks before any git writes."
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

_TOOL_ACTIVITY_TITLES: dict[str, str] = {
    "cancel_timers": "I'm cancelling timers.",
    "check_health": "I'm running a health check.",
    "create_pull_request": "I'm opening a pull request.",
    "list_files": "I'm listing files.",
    "list_internal_notes": "I'm reviewing internal notes.",
    "list_timers": "I'm checking timers.",
    "draft_improvement_plan": "I'm drafting an improvement plan.",
    "read_file": "I'm reading a file.",
    "run_python": "I'm running code.",
    "start_timer": "I'm setting a timer.",
    "write_file": "I'm writing a file.",
}

_TOOL_ACTIVITY_COMPLETED_TITLES: dict[str, str] = {
    "cancel_timers": "I cancelled timers.",
    "check_health": "I finished the health check.",
    "create_pull_request": "I opened a pull request.",
    "list_files": "I listed files.",
    "list_internal_notes": "I reviewed internal notes.",
    "list_timers": "I checked timers.",
    "draft_improvement_plan": "I drafted an improvement plan.",
    "read_file": "I read a file.",
    "run_python": "I ran code.",
    "start_timer": "I set a timer.",
    "write_file": "I wrote a file.",
}


_TOOL_ACTIVITY_FAILED_TITLES: dict[str, str] = {
    "draft_improvement_plan": IMPROVEMENT_PLAN_FAILED_TITLE,
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
            "timer": (SETTING_TIMER_TITLE, SETTING_TIMER_DETAIL),
        }
        return interaction_titles.get(interaction or "", (RECEIVED_TITLE, RECEIVED_DETAIL))
    return RECEIVED_TITLE, RECEIVED_DETAIL
