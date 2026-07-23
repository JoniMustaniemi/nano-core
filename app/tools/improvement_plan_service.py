from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from app.config import get_settings
from app.intents.self_improve import normalize_self_improve_goal
from app.memory import improvement_plans
from app.memory.internal_note_service import internal_note_service
from app.memory.models import InternalNote
from app.runtime.activity import activity
from app.runtime.status_copy import (
    DRAFTING_IMPROVEMENT_PLAN_DETAIL,
    DRAFTING_IMPROVEMENT_PLAN_TITLE,
)
from app.tools.files import read_text_file
from app.tools.self_improve_planning import (
    SELECT_JSON_HINT,
    complete_json_dict,
    fallback_files_for_goal,
    file_selection_lines,
    looks_like_llm_unavailable,
    parse_selection,
)

IMPROVEMENT_PLAN_MAX_FILES = 1
IMPROVEMENT_PLAN_COMPLETED_SOURCE = "tools.improvement_plan_service.completed"

PLAN_TEMPERATURE = 0.2


@dataclass(frozen=True, slots=True)
class ImprovementPlanResult:
    ok: bool
    step: str
    plan_id: int | None = None
    title: str | None = None
    goal: str | None = None
    error: str | None = None


def _validate_preferred_files(paths: list[str] | None, *, allowed: str) -> list[str]:
    if not paths:
        return []
    allowed_prefix = allowed.rstrip("/")
    validated: list[str] = []
    for raw_path in paths:
        path = str(raw_path).strip()
        if not path.startswith(allowed_prefix):
            continue
        try:
            read_text_file(path)
        except (OSError, ValueError):
            continue
        if path not in validated:
            validated.append(path)
    return validated


def _select_files(
    client: Any,
    *,
    goal: str,
    preferred_files: list[str] | None,
    allowed: str,
    max_files: int,
) -> list[str]:
    files_to_read = _validate_preferred_files(preferred_files, allowed=allowed)
    if files_to_read:
        return files_to_read[:max_files]

    selection_lines = file_selection_lines(goal)
    select_messages = [
        {
            "role": "system",
            "content": (
                "Select ONE file to review for a self-improvement plan. "
                f"Only paths under {allowed} are allowed. "
                f"Return JSON only: {SELECT_JSON_HINT} with exactly one path. "
                "Pick the single file most relevant to the goal. No markdown fences."
            ),
        },
        {
            "role": "user",
            "content": f"Goal: {goal}\n\nKnown files:\n" + "\n".join(selection_lines),
        },
    ]
    selection = complete_json_dict(
        client,
        select_messages,
        correction=(
            "Your previous response was invalid. Return JSON only with key files_to_read. "
            f"Example: {SELECT_JSON_HINT}"
        ),
    )
    files_to_read = parse_selection(selection) if selection is not None else []
    if not files_to_read:
        files_to_read = fallback_files_for_goal(goal, allowed=allowed)
    return files_to_read[:max_files]


def _read_file_contents(paths: list[str], *, allowed: str, max_file_chars: int) -> dict[str, str]:
    file_contents: dict[str, str] = {}
    allowed_prefix = allowed.rstrip("/")
    for raw_path in paths:
        path = str(raw_path)
        if not path.startswith(allowed_prefix):
            continue
        try:
            text = read_text_file(path)
        except (OSError, ValueError):
            continue
        if len(text) > max_file_chars:
            text = text[:max_file_chars]
        file_contents[path] = text
    return file_contents


def _build_plan_prompt(*, goal: str, file_contents: dict[str, str]) -> list[dict[str, str]]:
    sections = [f"Goal: {goal}", "", "Files reviewed:"]
    for path, content in file_contents.items():
        sections.extend([f"### {path}", content, ""])
    return [
        {
            "role": "system",
            "content": (
                "You draft focused improvement plans for Nano, a local AI assistant codebase. "
                "Write ONE plain-text plan about a single theme only. "
                "Do not bundle unrelated ideas, roadmaps, or multi-area refactors. "
                "Use these sections:\n"
                "- Summary (1-2 sentences about one improvement theme)\n"
                "- Target file (one file path)\n"
                "- Proposed change (2-4 short bullet steps, all about the same theme)\n"
                "- Risks (1-2 bullets)\n"
                "Do not edit code. Do not use markdown fences. "
                "Never list more than one target file."
            ),
        },
        {
            "role": "user",
            "content": "\n".join(sections),
        },
    ]


def _brief_theme(*, goal: str, title: str) -> str:
    for candidate in (title, goal):
        cleaned = normalize_self_improve_goal(str(candidate))
        if cleaned and cleaned.lower() not in {"improvement plan", "code update"}:
            return cleaned[:80]
    return "a codebase improvement"


def _plan_title(*, goal: str, files: list[str]) -> str:
    cleaned_goal = normalize_self_improve_goal(goal)
    if cleaned_goal:
        return cleaned_goal[:96]
    if files:
        return f"Improve {files[0]}"
    return "Improvement plan"


class ImprovementPlanService:
    """Draft text improvement plans without applying code changes."""

    def draft(
        self,
        *,
        client: Any,
        goal: str,
        preferred_files: list[str] | None = None,
        source_note_id: int | None = None,
    ) -> ImprovementPlanResult:
        if improvement_plans.has_unprocessed_plan():
            return ImprovementPlanResult(
                ok=False,
                step="gate",
                goal=goal,
                error="A plan is already waiting for review.",
            )

        settings = get_settings()
        allowed = settings.self_improve_allowed_prefix

        activity.working(
            title=DRAFTING_IMPROVEMENT_PLAN_TITLE,
            detail=DRAFTING_IMPROVEMENT_PLAN_DETAIL,
            source="tools.improvement_plan_service",
        )

        files_to_read = _select_files(
            client,
            goal=goal,
            preferred_files=preferred_files,
            allowed=allowed,
            max_files=IMPROVEMENT_PLAN_MAX_FILES,
        )
        if not files_to_read:
            return ImprovementPlanResult(
                ok=False,
                step="select",
                goal=goal,
                error="No files selected.",
            )

        file_contents = _read_file_contents(
            files_to_read,
            allowed=allowed,
            max_file_chars=settings.self_improve_max_file_chars,
        )
        if not file_contents:
            return ImprovementPlanResult(
                ok=False,
                step="read",
                goal=goal,
                error="Could not read target files.",
            )

        messages = _build_plan_prompt(goal=goal, file_contents=file_contents)
        raw = cast(
            str,
            client.complete(
                messages=messages,
                max_tokens=settings.self_improve_plan_max_tokens,
                temperature=PLAN_TEMPERATURE,
            ),
        ).strip()
        if looks_like_llm_unavailable(raw) or not raw:
            return ImprovementPlanResult(
                ok=False,
                step="draft",
                goal=goal,
                error="Could not draft an improvement plan.",
            )

        title = _plan_title(goal=goal, files=list(file_contents.keys()))
        plan = improvement_plans.create_plan(
            title=title,
            goal=goal,
            body=raw,
            files=list(file_contents.keys()),
            source_note_id=source_note_id,
        )
        theme = _brief_theme(goal=goal, title=title)
        activity.standby(
            title="I saved an improvement plan.",
            detail=f"Theme: {theme}. Open the Plans tab to read it.",
            source=IMPROVEMENT_PLAN_COMPLETED_SOURCE,
        )
        return ImprovementPlanResult(
            ok=True,
            step="complete",
            plan_id=plan.id,
            title=plan.title,
            goal=goal,
        )

    def draft_from_note(self, note: InternalNote, *, client: Any) -> ImprovementPlanResult:
        goal = internal_note_service.goal_from_internal_note(note)
        preferred_files = internal_note_service.preferred_files_from_note(note)
        result = self.draft(
            client=client,
            goal=goal,
            preferred_files=preferred_files or None,
            source_note_id=note.id,
        )
        if result.ok and note.id is not None:
            internal_note_service.mark_delivered(note.id)
        return result
