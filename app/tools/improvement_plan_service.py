from __future__ import annotations

import os
import re
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
    IMPROVEMENT_PLAN_FAILED_TITLE,
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

_SUMMARY_HEADER = re.compile(r"^[-*]?\s*summary\b\s*:?\s*$", re.IGNORECASE)
_ASSESSMENT_MARKERS = (
    "well-structured",
    "follows best practices",
    "is well organized",
    "is well-organized",
)


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


def _build_plan_prompt(
    *,
    goal: str,
    file_contents: dict[str, str],
    passive: bool = False,
) -> list[dict[str, str]]:
    sections = [f"Goal: {goal}", "", "Files reviewed:"]
    for path, content in file_contents.items():
        sections.extend([f"### {path}", content, ""])
    section_lines = [
        "- Summary (1-2 sentences about one improvement theme)\n",
        "- Target file (one file path)\n",
        "- Proposed change (2-4 short bullet steps, all about the same theme)\n",
    ]
    if not passive:
        section_lines.append("- Risks (1-2 bullets)\n")
    return [
        {
            "role": "system",
            "content": (
                "You draft focused improvement plans for Nano, a local AI assistant codebase. "
                "Write ONE plain-text plan about a single theme only. "
                "Do not bundle unrelated ideas, roadmaps, or multi-area refactors. "
                "Use these sections:\n"
                + "".join(section_lines)
                + "Do not edit code. Do not use markdown fences. "
                "Never list more than one target file."
            ),
        },
        {
            "role": "user",
            "content": "\n".join(sections),
        },
    ]


def _goal_reads_like_assessment(goal: str) -> bool:
    normalized = goal.strip().lower()
    if normalized.startswith("the file is"):
        return True
    return any(marker in normalized for marker in _ASSESSMENT_MARKERS)


def _summary_from_plan_body(body: str) -> str | None:
    lines = body.splitlines()
    collecting = False
    summary_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not collecting:
            if _SUMMARY_HEADER.match(stripped):
                collecting = True
            continue
        if not stripped:
            if summary_lines:
                break
            continue
        if stripped.endswith(":") and len(stripped) < 40 and not stripped.startswith("-"):
            break
        if re.match(r"^[-*]?\s*(target file|proposed change|risks)\b", stripped, re.IGNORECASE):
            break
        summary_lines.append(stripped)
    if not summary_lines:
        return None
    summary = " ".join(summary_lines)
    summary = " ".join(summary.split())
    if not summary:
        return None
    return summary[:96]


def _brief_theme(*, goal: str, title: str) -> str:
    for candidate in (title, goal):
        cleaned = normalize_self_improve_goal(str(candidate))
        if cleaned and cleaned.lower() not in {"improvement plan", "code update"}:
            return cleaned[:80]
    return "a codebase improvement"


def _plan_title(*, goal: str, files: list[str], body: str | None = None) -> str:
    if body:
        from_body = _summary_from_plan_body(body)
        if from_body:
            return from_body
    cleaned_goal = normalize_self_improve_goal(goal)
    if cleaned_goal and not _goal_reads_like_assessment(cleaned_goal):
        return cleaned_goal[:96]
    if files:
        return f"Improve {os.path.basename(files[0])}"
    if cleaned_goal:
        return cleaned_goal[:96]
    return "Improvement plan"


def _finalize_draft_activity(result: ImprovementPlanResult, *, theme: str | None = None) -> None:
    if result.step == "gate":
        return
    if result.ok:
        activity.standby(
            title="I saved an improvement plan.",
            detail=f"Theme: {theme or 'a codebase improvement'}. Open the Plans tab to read it.",
            source=IMPROVEMENT_PLAN_COMPLETED_SOURCE,
        )
        return
    activity.standby(
        title=IMPROVEMENT_PLAN_FAILED_TITLE,
        detail=result.error or "Could not draft an improvement plan.",
        source="tools.improvement_plan_service",
    )


class ImprovementPlanService:
    """Draft text improvement plans without applying code changes."""

    def draft(
        self,
        *,
        client: Any,
        goal: str,
        preferred_files: list[str] | None = None,
        source_note_id: int | None = None,
        passive: bool = False,
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

        try:
            return self._draft_after_working(
                client=client,
                goal=goal,
                preferred_files=preferred_files,
                source_note_id=source_note_id,
                passive=passive,
                allowed=allowed,
            )
        except Exception:
            result = ImprovementPlanResult(
                ok=False,
                step="draft",
                goal=goal,
                error="Could not draft an improvement plan.",
            )
            _finalize_draft_activity(result)
            return result

    def _draft_after_working(
        self,
        *,
        client: Any,
        goal: str,
        preferred_files: list[str] | None,
        source_note_id: int | None,
        passive: bool,
        allowed: str,
    ) -> ImprovementPlanResult:
        settings = get_settings()
        files_to_read = _select_files(
            client,
            goal=goal,
            preferred_files=preferred_files,
            allowed=allowed,
            max_files=IMPROVEMENT_PLAN_MAX_FILES,
        )
        if not files_to_read:
            result = ImprovementPlanResult(
                ok=False,
                step="select",
                goal=goal,
                error="No files selected.",
            )
            _finalize_draft_activity(result)
            return result

        file_contents = _read_file_contents(
            files_to_read,
            allowed=allowed,
            max_file_chars=settings.self_improve_max_file_chars,
        )
        if not file_contents:
            result = ImprovementPlanResult(
                ok=False,
                step="read",
                goal=goal,
                error="Could not read target files.",
            )
            _finalize_draft_activity(result)
            return result

        messages = _build_plan_prompt(
            goal=goal,
            file_contents=file_contents,
            passive=passive,
        )
        raw = cast(
            str,
            client.complete(
                messages=messages,
                max_tokens=settings.self_improve_plan_max_tokens,
                temperature=PLAN_TEMPERATURE,
            ),
        ).strip()
        if looks_like_llm_unavailable(raw) or not raw:
            result = ImprovementPlanResult(
                ok=False,
                step="draft",
                goal=goal,
                error="Could not draft an improvement plan.",
            )
            _finalize_draft_activity(result)
            return result

        file_list = list(file_contents.keys())
        title = _plan_title(goal=goal, files=file_list, body=raw)
        plan = improvement_plans.create_plan(
            title=title,
            goal=goal,
            body=raw,
            files=file_list,
            source_note_id=source_note_id,
        )
        theme = _brief_theme(goal=goal, title=title)
        result = ImprovementPlanResult(
            ok=True,
            step="complete",
            plan_id=plan.id,
            title=plan.title,
            goal=goal,
        )
        _finalize_draft_activity(result, theme=theme)
        return result

    def draft_from_note(self, note: InternalNote, *, client: Any) -> ImprovementPlanResult:
        goal = internal_note_service.goal_from_internal_note(note)
        preferred_files = internal_note_service.preferred_files_from_note(note)
        return self.draft(
            client=client,
            goal=goal,
            preferred_files=preferred_files or None,
            source_note_id=note.id,
            passive=True,
        )
