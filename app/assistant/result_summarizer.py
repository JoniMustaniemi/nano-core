import json
from typing import Any, cast

from app.assistant.prompts import SYSTEM_PROMPT
from app.assistant.response_guard import enforce_user_facing_answer


class ToolResultSummarizer:
    def summarize(
        self,
        *,
        client: Any,
        user_message: str,
        tool_name: str,
        tool_result: str,
    ) -> str:
        """
        Summarize the requested operation.

        Args:
            client: LLM client used to generate responses.
            user_message: User message value.
            tool_name: Registered tool name.
            tool_result: Serialized tool result to summarize.

        Returns:
            Generated or formatted string value.
        """
        if tool_name == "check_health":
            return self._summarize_health_result(tool_result)

        summary_messages = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + " Summarize the tool result for the user in plain, natural language. "
                    + "Do not read raw JSON aloud. Do not invent facts."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User request: {user_message}\n\n"
                    f"Tool used: {tool_name}\n"
                    f"Tool result:\n{tool_result}"
                ),
            },
        ]
        summary = cast(str, client.complete(messages=summary_messages)).strip()
        if not summary:
            return "The procedure finished, though the summary failed to materialize."
        return enforce_user_facing_answer(client, user_message, summary)

    def _summarize_health_result(self, tool_result: str) -> str:
        """
        Return a deterministic first-person health diagnostic summary.

        Args:
            tool_result: Serialized tool result to summarize.

        Returns:
            Generated or formatted string value.
        """
        try:
            payload = json.loads(tool_result)
        except json.JSONDecodeError:
            return "I could not read my diagnostic result."

        checks = payload.get("checks", [])
        if not checks:
            return "My diagnostics returned no checks to report."

        failing_checks = [
            check for check in checks if str(check.get("status", "unknown")).lower() != "ok"
        ]
        if not failing_checks:
            return "My diagnostics are clear. No issues were found."

        lines = []
        for check in failing_checks:
            name = str(check.get("name", "unknown"))
            detail = str(check.get("detail", "")).strip()
            if detail:
                lines.append(f"My {name} check is failing: {detail}")
            else:
                lines.append(f"My {name} check is failing.")
        return " ".join(lines)
