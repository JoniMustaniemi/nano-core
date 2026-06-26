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
                    + "For health checks, only report problems. Do not mention checks that "
                    + "passed unless every check passed, in which case give a short all-clear. "
                    + "Do not introduce yourself, describe your personality, or explain what "
                    + "kind of assistant you are. "
                    + "Do not say you will continue running checks or provide later results; "
                    + "the tool result is already final for this request. "
                    + "Do not start with a title or label; answer as yourself. "
                    + "If everything is fine, say so simply. "
                    + "If something needs attention, describe only the meaningful issues clearly "
                    + "and accurately. "
                    + "Do not invent failures, thresholds, comparisons, or numbers."
                    + "add subtle personality to the answer, but do not overdo it."

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
        if not summary:
            return "The procedure finished, though the summary failed to materialize."
        if tool_name == "check_health":
            summary = self._enforce_health_failure_details(
                client=client,
                user_message=user_message,
                summary_input=summary_input,
                summary=summary,
            )
        return enforce_user_facing_answer(client, user_message, summary)

    def _enforce_health_failure_details(
        self,
        *,
        client: Any,
        user_message: str,
        summary_input: str,
        summary: str,
    ) -> str:
        """
        Ensure failing health checks are named in the summary.

        Args:
            client: LLM client used to revise responses.
            user_message: User message value.
            summary_input: Prepared health summary input.
            summary: Model-generated health summary.

        Returns:
            Original summary, or revised summary with failure details.
        """
        failures = self._health_failures_from_summary_input(summary_input)
        if not failures:
            return summary

        lowered_summary = summary.lower()
        missing_failures = [
            failure for failure in failures if failure["name"].lower() not in lowered_summary
        ]
        if not missing_failures:
            return summary

        failure_lines = "\n".join(
            f"- {failure['name']}: {failure['detail']}" for failure in failures
        )
        messages = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + " Rewrite the health diagnostic answer. The previous answer was too vague. "
                    + "When a health check fails, you must name each failing check and include "
                    + "the provided detail. Do not mention checks that passed. Do not introduce "
                    + "yourself. Do not promise later results or continued checking. Do not "
                    + "invent causes or extra numbers. Return only the revised answer with a "
                    + "subtle personality twist."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User request: {user_message}\n\n"
                    f"Failing checks:\n{failure_lines}\n\n"
                    f"Previous vague answer:\n{summary}"
                ),
            },
        ]
        revised = cast(str, client.complete(messages=messages)).strip()
        return revised or summary

    def _health_summary_input(self, tool_result: str) -> str:
        """
        Return service health information.

        Args:
            tool_result: Serialized tool result to summarize.

        Returns:
            Generated or formatted string value.
        """
        try:
            payload = json.loads(tool_result)
        except json.JSONDecodeError:
            return tool_result

        checks = payload.get("checks", [])
        failing_checks = [
            check for check in checks if str(check.get("status", "unknown")).lower() != "ok"
        ]
        lines = [
            "This is Nano reporting on my own health.",
            f"My overall status is {payload.get('overall', 'unknown')}.",
        ]
        if not failing_checks:
            lines.append("No problems were found.")
            return "\n".join(lines)

        lines.append("Problems found:")
        for check in failing_checks:
            name = str(check.get("name", "unknown"))
            status = str(check.get("status", "unknown"))
            detail = str(check.get("detail", "")).strip()
            lines.append(f"- My {name} check is {status}. {detail}")
        return "\n".join(lines)

    def _health_failures_from_summary_input(self, summary_input: str) -> list[dict[str, str]]:
        """
        Return failing checks from prepared health summary text.

        Args:
            summary_input: Prepared health summary input.

        Returns:
            List of failing check name/detail dictionaries.
        """
        failures: list[dict[str, str]] = []
        for line in summary_input.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- My ") or " check is " not in stripped:
                continue
            name_part, detail_part = stripped[5:].split(" check is ", 1)
            status_part, _, detail = detail_part.partition(".")
            if status_part.strip().lower() == "ok":
                continue
            failures.append(
                {
                    "name": name_part.strip(),
                    "detail": detail.strip(),
                }
            )
        return failures
