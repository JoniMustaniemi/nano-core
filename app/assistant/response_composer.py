from __future__ import annotations

import json

from app.assistant.prompts import COMPOSE_HINTS, RESPONSE_COMPOSER_PROMPT
from app.assistant.response_source import ResponseSource
from app.assistant.rules import system_confirmation_prompt, wipe_confirmation_prompt
from app.llm.protocol import LLMClient


class ResponseComposer:
    """
    Turn structured facts into Nano-voiced text before the guard pass runs.
    """

    def compose(self, client: LLMClient, source: ResponseSource) -> str:
        """
        Turn structured facts into a Nano-voiced reply.

        Args:
            client: LLM client used for composition when needed.
            source: Structured response input.

        Returns:
            User-facing assistant text before guarding.
        """
        if source.kind in {"follow_up", "confirmation", "answer"}:
            if source.kind == "confirmation":
                return self._compose_confirmation(source)
            return source.facts

        if source.kind == "tool_result" and source.tool_name == "check_health":
            return self._compose_health_result(source.facts)

        if source.kind == "tool_result" and source.tool_name in COMPOSE_HINTS:
            return self._compose_with_hint(client, source)

        if source.kind in {"tool_result", "tool_error"} and not self._looks_like_json(source.facts):
            return source.facts

        return self._compose_with_llm(client, source)

    def _compose_confirmation(self, source: ResponseSource) -> str:
        """
        Compose a destructive-action confirmation prompt.

        Args:
            source: Confirmation response source.

        Returns:
            Confirmation prompt text.
        """
        if source.confirmation_action is not None:
            return system_confirmation_prompt(source.confirmation_action, source.user_message)
        if not source.facts.startswith("User requested:"):
            return source.facts
        return wipe_confirmation_prompt(source.user_message)

    def _compose_with_hint(self, client: LLMClient, source: ResponseSource) -> str:
        """
        Compose a tool result using a registered compose hint.

        Args:
            client: LLM client used for composition.
            source: Tool result response source.

        Returns:
            Composed user-facing text.
        """
        hint = COMPOSE_HINTS.get(source.tool_name or "", "")
        system_prompt = RESPONSE_COMPOSER_PROMPT
        if hint:
            system_prompt = f"{system_prompt}\n\n{hint}"
        summary_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (f"User request: {source.user_message}\n\nTool result:\n{source.facts}"),
            },
        ]
        summary = client.complete(messages=summary_messages).strip()
        if not summary:
            return "The procedure finished, though the summary failed to materialize."
        return summary

    def _compose_with_llm(self, client: LLMClient, source: ResponseSource) -> str:
        """
        Compose a tool or error result with the shared personality prompt.

        Args:
            client: LLM client used for composition.
            source: Response source with factual payload.

        Returns:
            Composed user-facing text.
        """
        kind_label = {
            "tool_result": "tool result",
            "tool_error": "tool error",
            "answer": "answer draft",
            "follow_up": "follow-up",
            "confirmation": "confirmation",
        }[source.kind]
        tool_line = f"Tool: {source.tool_name}\n" if source.tool_name else ""
        summary_messages = [
            {"role": "system", "content": RESPONSE_COMPOSER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"User request: {source.user_message}\n"
                    f"Response kind: {kind_label}\n"
                    f"{tool_line}"
                    f"Factual payload:\n{source.facts}"
                ),
            },
        ]
        summary = client.complete(messages=summary_messages).strip()
        if not summary:
            if source.kind == "tool_error":
                return self._tool_error_fallback(source)
            return "The procedure finished, though the summary failed to materialize."
        return summary

    def _compose_health_result(self, tool_result: str) -> str:
        """
        Return a deterministic first-person health diagnostic summary.

        Args:
            tool_result: Serialized health check JSON.

        Returns:
            Health summary text.
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

    def _tool_error_fallback(self, source: ResponseSource) -> str:
        """
        Build a fallback tool error message.

        Args:
            source: Tool error response source.

        Returns:
            Fallback error text.
        """
        try:
            payload = json.loads(source.facts)
        except json.JSONDecodeError:
            return f"I could not complete {source.tool_name or 'the requested action'}."
        error = str(payload.get("error", "")).strip()
        if error:
            return error
        return f"I could not complete {source.tool_name or 'the requested action'}."

    def _looks_like_json(self, value: str) -> bool:
        """
        Return whether a string looks like JSON.

        Args:
            value: Candidate string.

        Returns:
            True when the value appears to be JSON.
        """
        stripped = value.strip()
        if not stripped.startswith(("{", "[")):
            return False
        try:
            json.loads(stripped)
        except json.JSONDecodeError:
            return False
        return True
