from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def patch_announce_voice(
    monkeypatch: MonkeyPatch,
    collector: list[str],
) -> None:
    from app.runtime.activity import activity

    def _record(message: str) -> None:
        collector.append(message)

    monkeypatch.setattr(activity, "announce_voice", _record)


def silence_announce_voice(monkeypatch: MonkeyPatch) -> None:
    from app.runtime.activity import activity

    monkeypatch.setattr(activity, "announce_voice", lambda message: None)
