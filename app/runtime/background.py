from __future__ import annotations

from collections.abc import Callable
from threading import Thread
from typing import Any


def run_background(fn: Callable[[], Any], *, label: str) -> Thread:
    """Run a callable on a tracked non-daemon background thread."""
    thread = Thread(target=fn, name=label, daemon=False)
    thread.start()
    return thread
