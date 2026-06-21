from __future__ import annotations

import json
import re
from typing import Any, cast

from app.assistant.prompts import SYSTEM_PROMPT


class ToolResultSummarizer:
    def summarize(
        self,
        *,
        client: Any,
        user_message: str,
        tool_name: str,
        tool_result: str,
    ) -> str:
        summary_input = tool_result
        if tool_name == "check_health":
            summary_input = self._health_summary_input(tool_result)

        summary_messages = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + " Summarize the tool result for the user in plain, natural language. "
                    + "Do not read raw JSON aloud. "
                    + "Do not narrate field names, quote status labels, or list every check "
                    + "mechanically. "
                    + "If you are describing your own status, speak in first person as Nano, "
                    + "not in third person. "
                    + "Do not refer to Nano as the user, the assistant, a report, or "
                    + "Nano's self-diagnostics. "
                    + "Do not start with a title or label; answer as yourself. "
                    + "If everything is fine, say so simply. "
                    + "If something needs attention, describe only the meaningful issues clearly "
                    + "and accurately. "
                    + "Do not invent failures, thresholds, comparisons, or numbers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User request: {user_message}\n\n"
                    f"Tool used: {tool_name}\n"
                    f"Tool result:\n{summary_input}"
                ),
            },
        ]
        summary = cast(str, client.complete(messages=summary_messages)).strip()
        if tool_name == "check_health":
            summary = self._sanitize_self_reference(summary)
        return summary or "The procedure finished, though the summary failed to materialize."

    def _health_summary_input(self, tool_result: str) -> str:
        try:
            payload = json.loads(tool_result)
        except json.JSONDecodeError:
            return tool_result

        checks = payload.get("checks", [])
        lines = [
            "This is Nano reporting on my own health.",
            f"My overall status is {payload.get('overall', 'unknown')}.",
        ]
        for check in checks:
            name = str(check.get("name", "unknown"))
            status = str(check.get("status", "unknown"))
            detail = str(check.get("detail", "")).strip()
            lines.append(f"- My {name} check is {status}. {detail}")
        return "\n".join(lines)

    def _sanitize_self_reference(self, summary: str) -> str:
        replacements = {
            r"\bthe user's system\b": "my system",
            r"\buser's system\b": "my system",
            r"\bthe user system\b": "my system",
            r"\bthe user's diagnostics report\b": "my diagnostics",
            r"\bthe user's diagnostics\b": "my diagnostics",
            r"\bnano's self-diagnostics report:\s*": "",
            r"\bnano's diagnostics report:\s*": "",
            r"\bself-diagnostics report:\s*": "",
        }
        cleaned = summary
        for pattern, replacement in replacements.items():
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
        return re.sub(r"(^|[.!?]\s+)my\b", lambda match: f"{match.group(1)}My", cleaned)
