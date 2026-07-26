from __future__ import annotations

import re
from dataclasses import dataclass

_SECTION_HEADER = re.compile(
    r"^[-*]?\s*(summary|target file|proposed changes?|risks)\b\s*:?\s*$",
    re.IGNORECASE,
)
_TARGET_FILE_LINE = re.compile(r"^[-*]?\s*(.+)$")


@dataclass(frozen=True, slots=True)
class ParsedPlanBody:
    summary: str
    target_file: str | None
    proposed_changes: list[str]
    risks: list[str]


def _normalize_section_name(header: str) -> str | None:
    cleaned = header.strip().lower().rstrip(":")
    if cleaned == "summary":
        return "summary"
    if cleaned == "target file":
        return "target_file"
    if cleaned.startswith("proposed change"):
        return "proposed_change"
    if cleaned == "risks":
        return "risks"
    return None


def _strip_bullet(line: str) -> str:
    return re.sub(r"^[-*]\s+", "", line.strip())


def parse_plan_body(body: str) -> ParsedPlanBody:
    """Parse a drafted improvement plan body into structured sections."""
    summary_lines: list[str] = []
    target_file: str | None = None
    proposed_changes: list[str] = []
    risks: list[str] = []
    current_section: str | None = None

    for raw_line in body.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            if current_section == "summary" and summary_lines:
                current_section = None
            continue

        if _SECTION_HEADER.match(stripped):
            current_section = _normalize_section_name(stripped)
            continue

        if current_section == "summary":
            summary_lines.append(stripped)
            continue

        if current_section == "target_file":
            if target_file is None:
                match = _TARGET_FILE_LINE.match(stripped)
                candidate = match.group(1).strip() if match else stripped
                if candidate and not candidate.endswith(":"):
                    target_file = candidate
            continue

        if current_section == "proposed_change":
            bullet = _strip_bullet(stripped)
            if bullet:
                proposed_changes.append(bullet)
            continue

        if current_section == "risks":
            bullet = _strip_bullet(stripped)
            if bullet:
                risks.append(bullet)

    summary = " ".join(summary_lines).strip()
    return ParsedPlanBody(
        summary=summary,
        target_file=target_file,
        proposed_changes=proposed_changes,
        risks=risks,
    )


def target_file_mismatch_warning(
    parsed: ParsedPlanBody,
    *,
    allowed_files: list[str],
) -> str | None:
    if parsed.target_file is None:
        return None
    normalized_allowed = {path.replace("\\", "/") for path in allowed_files}
    normalized_target = parsed.target_file.replace("\\", "/")
    if normalized_target not in normalized_allowed:
        return (
            f"Plan target file ({parsed.target_file}) does not match "
            f"allowed files ({', '.join(allowed_files)})."
        )
    return None
