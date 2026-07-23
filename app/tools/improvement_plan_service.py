from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from app.config import get_settings
from app.memory import improvement_plans
from app.memory.internal_note_service import internal_note_service
from app.memory.models import InternalNote
from app.runtime.activity import activity
from app.runtime.long_task_progress import LongTaskProgressReporter
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
                "Select files to review for a self-improvement plan. "
                f"Only paths under {allowed} are allowed. "
                f"Return JSON only: {SELECT_JSON_HINT} with at most "
                f"{max_files} paths. No markdown fences."
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
                "You draft improvement plans for Nano, a local AI assistant codebase. "
                "Write a readable plain-text plan with these sections:\n"
                "- Summary\n"
                "- Files to change\n"
                "- Proposed changes (per file)\n"
                "- Risks / things to verify\n"
                "Do not edit code. Do not use markdown fences. Keep it concise and actionable."
            ),
        },
        {
            "role": "user",
            "content": "\n".join(sections),
        },
    ]


def _plan_title(*, goal: str, files: list[str]) -> str:
    cleaned_goal = " ".join(goal.strip().split())
    if cleaned_goal:
        return cleaned_goal[:120]
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

        with LongTaskProgressReporter(task_name="improvement-plan", goal=goal) as progress:
            progress.update(step="starting")
            activity.working(
                title=DRAFTING_IMPROVEMENT_PLAN_TITLE,
                detail=DRAFTING_IMPROVEMENT_PLAN_DETAIL,
                source="tools.improvement_plan_service",
            )

            progress.update(step="select")
            files_to_read = _select_files(
                client,
                goal=goal,
                preferred_files=preferred_files,
                allowed=allowed,
                max_files=settings.self_improve_max_files,
            )
            if not files_to_read:
                return ImprovementPlanResult(
                    ok=False,
                    step="select",
                    goal=goal,
                    error="No files selected.",
                )

            progress.update(step="read")
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

            progress.update(step="draft")
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
            activity.log(
                title="I drafted an improvement plan.",
                detail=title,
                source="tools.improvement_plan_service",
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
