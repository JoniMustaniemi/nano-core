from __future__ import annotations

import inspect
import re

from app.runtime import status_copy
from app.tools.registry import list_tools

_SELF_REF_NANO = re.compile(r"\bnano\b", re.IGNORECASE)

# Wake-phrase references and user-facing product labels are allowed.
_ALLOWED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'say\s+"hey nano"\s+when ready', re.IGNORECASE),
)


def _allows_nano_mention(text: str) -> bool:
    return any(pattern.search(text) for pattern in _ALLOWED_PATTERNS)


def _assert_first_person_copy(text: str, *, context: str) -> None:
    if _allows_nano_mention(text):
        return
    if _SELF_REF_NANO.search(text):
        raise AssertionError(f"Third-person Nano reference in {context}: {text!r}")


def _iter_status_copy_strings() -> list[tuple[str, str]]:
    strings: list[tuple[str, str]] = []
    for name, value in inspect.getmembers(status_copy):
        if name.startswith("_"):
            continue
        if isinstance(value, str):
            strings.append((name, value))
        elif isinstance(value, tuple):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    strings.append((f"{name}[{index}]", item))
        elif isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str):
                    strings.append((f"{name}[{key!r}]", item))
    strings.extend(
        (key, value)
        for key, value in status_copy.client_copy_payload().items()
        if isinstance(value, str)
    )
    return strings


_FLOW_FACT_STRINGS: tuple[str, ...] = (
    "Reply yes to restart my service, or no to cancel.",
    "Restarting my service now.",
)


def test_status_copy_avoids_third_person_nano() -> None:
    for name, text in _iter_status_copy_strings():
        _assert_first_person_copy(text, context=f"status_copy.{name}")


def test_tool_ui_copy_avoids_third_person_nano() -> None:
    for tool in list_tools():
        for field in ("announcement", "ui_message", "ui_description", "description"):
            value = getattr(tool, field, "")
            if value:
                _assert_first_person_copy(value, context=f"tool.{tool.name}.{field}")


def test_flow_facts_avoid_third_person_nano() -> None:
    for text in _FLOW_FACT_STRINGS:
        _assert_first_person_copy(text, context="flow facts")
