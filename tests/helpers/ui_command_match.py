"""Mirror of client-side UI command phrase matching in home-ui.js.

Keep regex patterns in sync with nano-ui/static/home-ui.js when updating either file.
"""

from __future__ import annotations

import re
from typing import Any

PLANS_SECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^(open|show|go to)(\s+the)?\s+plans(\s+(tab|section|panel|view))?$",
        r"^(open|show|go to)(\s+the)?\s+improvement plans$",
        r"^(what|show|tell|list)(\s+are)?(\s+my)?\s+(improvement plans|plans)$",
        r"\bwhat\s+have\s+you\s+planned\b",
        r"\bwhat\s+do\s+you\s+have\s+planned\b",
        r"\bwhat\s+plans\s+do\s+you\s+have\b",
        r"\bwhat\s+(plans|improvement plans)\b",
        r"\b(your|any|the)\s+(plans|improvement plans)\b",
        r"\b(show|see|view|open|look at|display|pull up|bring up)\b.*\b(plans|improvement plans)\b",
        r"\b(can|could|may|would|let)\s+(i|me|we)\s+(see|view|look at|open|show|have)\b.*\b(plans|improvement plans)\b",
        r"\bwhat\s+(is|are)\s+in\s+(the\s+)?plans\b",
        r"\btake\s+me\s+to\s+(the\s+)?plans(\s+(tab|section|panel|view))?\b",
        r"\bgo\s+to\s+(the\s+)?plans\s+tab\b",
    )
)

BRAINS_SECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^(open|show|go to)(\s+the)?\s+brains(\s+(tab|section|panel|view))?$",
        r"^(open|show)(\s+the)?\s+internal notes$",
        r"\bwhat\s+are\s+you\s+thinking\b",
        r"\bwhat\s+you\s+are\s+thinking\b",
        r"\bwhat\s+you\s+re\s+thinking\b",
        r"\bwhats\s+on\s+your\s+mind\b",
        r"\bwhat\s+is\s+on\s+your\s+mind\b",
        r"\b(show|see|view|open|look at|display|pull up|bring up)\b.*\b(your thoughts|your mind|internal notes|activity log|brains)\b",
        r"\b(can|could|may|would|let)\s+(i|me|we)\s+(see|view|look at|open|show|have)\b.*\b(your thoughts|your mind|internal notes|activity log|brains)\b",
        r"\bwhat\s+(is|are)\s+in\s+(your\s+)?(mind|brains|activity)\b",
        r"\bwhat\s+have\s+you\s+been\s+thinking\b",
        r"\blet\s+me\s+see\s+your\s+brains\b",
    )
)

STORAGE_SECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^(open|show|go to)(\s+the)?\s+(stored data|storage|data)(\s+(tab|section|panel|view))?$",
        r"\bwhat\s+(is|are)\s+in\s+(the\s+)?(storage|stored data|saved data)\b",
        r"\b(show|see|view|open|look at|display|pull up|bring up)\b.*\b(saved data|stored data|storage|saved stuff)\b",
        r"\b(can|could|may|would|let)\s+(i|me|we)\s+(see|view|look at|open|show|have)\b.*\b(saved data|stored data|storage|saved stuff)\b",
        r"\bcan\s+i\s+see\b.*\b(saved|stored)\s+data\b",
        r"\bwhat\s+data\s+(do\s+you\s+have|is\s+saved|have\s+you\s+saved)\b",
        r"\bwhat\s+did\s+you\s+save\b",
        r"\bshow\s+me\s+what\s+you\s+saved\b",
    )
)

COMMANDS_SECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^(open|show)(\s+the)?\s+(commands|quick actions)(\s+(drawer|panel|view|list|menu))?$",
        r"\b(show|see|view|open|list)\b.*\b(commands|quick actions|command list)\b",
        r"\b(can|could|may|would|let)\s+(i|me|we)\s+(see|view|look at|open|show|have|list)\b.*\b(commands|quick actions|command list)\b",
        r"\bwhat\s+commands\b",
        r"\bwhat\s+commands\s+are\s+available\b",
        r"\blist\s+commands\b",
        r"\bopen\s+(the\s+)?command\s+list\b",
    )
)

CONTROLS_HIDE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^hide(\s+the)?\s+controls?(\s+(panel|menu|bar))?$",
        r"^hide(\s+the)?\s+ui\s+controls?$",
        r"\bhide\b.*\bcontrols\b",
        r"\b(can|could|may|would|let)\s+(i|me|we|you)\s+hide\b.*\bcontrols\b",
    )
)

CONTROLS_SHOW_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^show(\s+the)?\s+controls?(\s+(panel|menu|bar))?$",
        r"^show(\s+the)?\s+ui\s+controls?$",
        r"\b(show|see|view|open|look at|display|pull up|bring up)\b.*\bcontrols\b",
        r"\b(can|could|may|would|let)\s+(i|me|we)\s+(see|view|look at|open|show|have)\b.*\bcontrols\b",
        r"\bopen(\s+the)?\s+controls(\s+(panel|menu|bar))?\b",
    )
)

CONTROLS_TOGGLE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern) for pattern in (r"^(hide\s*/\s*show|toggle)(\s+the)?\s+controls?$",)
)

CLOSE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern)
    for pattern in (
        r"^close$",
        r"^hide$",
        r"^go back$",
        r"^dismiss$",
        r"^exit$",
        r"^close panel$",
        r"^close this$",
        r"^close it$",
        r"^exit panel$",
        r"^close(\s+the)?\s+(panel|sheet|drawer|view|modal)$",
        r"^close(\s+the)?\s+(plans|brains|storage|commands)(\s+(tab|panel|drawer|section))?$",
        r"^dismiss(\s+the)?\s+(panel|sheet|drawer|view|modal)$",
        r"^hide(\s+the)?\s+(panel|view|this|modal)$",
        r"\b(you can|can you|could you|please)\s+close\b",
        r"\b(okay|ok)\b.*\bclose\b",
        r"\b(thanks|thank you)\b.*\b(close|dismiss)\b",
        r"\b(close|dismiss|hide)\b.*\b(menu|panel|view|modal|this|it|screen|window)\b",
        r"\b(menu|panel|view|modal|this|it|screen)\b.*\b(close|dismiss|hide)\b",
        r"\b(close|dismiss|hide)\b.*\b(plans|brains|storage|commands)\b",
    )
)


def is_close_command_negated(normalized: str) -> bool:
    return re.search(r"\b(?:don t|do not|dont|never)\s+close\b", normalized) is not None


def matches_close_command(message: str) -> bool:
    normalized = normalize_ui_command_text(message)
    if not normalized or is_close_command_negated(normalized):
        return False
    return _matches_patterns(normalized, CLOSE_PATTERNS)


def normalize_ui_command_text(message: str) -> str:
    lowered = message.strip().lower()
    lowered = re.sub(r"[.!?,]+", " ", lowered)
    lowered = re.sub(r"[''´`]", "", lowered)
    lowered = re.sub(r"\b(hey|hi)\s+nano\b", " ", lowered)
    lowered = re.sub(r"\bnano\b", " ", lowered)
    lowered = re.sub(r"\bplease\b", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _matches_patterns(normalized: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(normalized) for pattern in patterns)


def match_ui_command(message: str) -> dict[str, Any] | None:
    normalized = normalize_ui_command_text(message)
    if not normalized:
        return None

    if normalized == "hide show controls" or _matches_patterns(
        normalized, CONTROLS_TOGGLE_PATTERNS
    ):
        return {"type": "controls", "action": "toggle"}

    if _matches_patterns(normalized, CONTROLS_HIDE_PATTERNS):
        return {"type": "controls", "action": "hide"}

    if _matches_patterns(normalized, CONTROLS_SHOW_PATTERNS):
        return {"type": "controls", "action": "show"}

    if matches_close_command(message):
        return {"type": "close"}

    if _matches_patterns(normalized, PLANS_SECTION_PATTERNS):
        return {"type": "section", "target": "plans"}

    if _matches_patterns(normalized, BRAINS_SECTION_PATTERNS):
        return {"type": "section", "target": "brains"}

    if _matches_patterns(normalized, STORAGE_SECTION_PATTERNS):
        return {"type": "section", "target": "storage"}

    if _matches_patterns(normalized, COMMANDS_SECTION_PATTERNS):
        return {"type": "section", "target": "commands"}

    return None
