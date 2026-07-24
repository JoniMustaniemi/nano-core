from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Event, RLock, Thread
from typing import Any

from app.runtime.activity import activity

LONG_TASK_PROGRESS_INTERVAL_SECONDS = 120
LONG_TASK_PROGRESS_SOURCE = "runtime.long_task_progress"
_PROGRESS_POLL_SECONDS = 5

_FILE_LABELS: dict[str, str] = {
    "app/assistant/rules/messages.py": "the message helpers",
    "app/runtime/status_copy.py": "the status messages",
    "app/assistant/flows/timer.py": "the timer flow",
}


@dataclass
class LongTaskProgress:
    task_name: str = ""
    goal: str = ""
    step: str = "starting"
    current_file: str | None = None
    file_index: int = 0
    file_count: int = 0
    attempt: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class ProgressAnnouncement:
    title: str
    detail: str | None
    spoken: str


def _file_label(path: str | None) -> str:
    if not path:
        return "the target file"
    if path in _FILE_LABELS:
        return _FILE_LABELS[path]
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".py"):
        return f"the {name[:-3].replace('_', ' ')} module"
    return f"the {name} file"


def _attempt_phrase(attempt: int) -> str:
    if attempt <= 0:
        return ""
    words = {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
    }
    word = words.get(attempt, str(attempt))
    return f", attempt {word}"


def format_progress_update(progress: LongTaskProgress) -> ProgressAnnouncement:
    task = progress.task_name or "this task"
    prefix = f"I'm still working on {task}."

    if progress.step == "select":
        spoken = f"{prefix} I'm choosing which files to edit."
        return ProgressAnnouncement(
            title="Still improving myself.",
            detail="Choosing which files to edit.",
            spoken=spoken,
        )

    if progress.step == "plan":
        label = _file_label(progress.current_file)
        attempt = _attempt_phrase(progress.attempt)
        file_position = ""
        if progress.file_count > 1:
            file_position = f" (file {progress.file_index} of {progress.file_count})"
        detail = f"Drafting changes to {progress.current_file or label}{file_position}{attempt}."
        spoken = f"{prefix} I'm drafting changes to {label}{attempt}."
        return ProgressAnnouncement(
            title="Still improving myself.",
            detail=detail,
            spoken=spoken,
        )

    if progress.step == "lint":
        spoken = f"{prefix} I'm running lint checks."
        return ProgressAnnouncement(
            title="Still improving myself.",
            detail="Running lint checks.",
            spoken=spoken,
        )

    if progress.step == "verify":
        spoken = f"{prefix} I'm running verification checks."
        return ProgressAnnouncement(
            title="Still improving myself.",
            detail="Running verification checks.",
            spoken=spoken,
        )

    if progress.step == "pr":
        spoken = f"{prefix} I'm preparing the pull request."
        return ProgressAnnouncement(
            title="Still improving myself.",
            detail="Preparing the pull request.",
            spoken=spoken,
        )

    spoken = f"{prefix} I'm getting started."
    return ProgressAnnouncement(
        title="Still improving myself.",
        detail="Getting started.",
        spoken=spoken,
    )


class LongTaskProgressReporter:
    """Emit periodic activity updates for long-running work without blocking it."""

    def __init__(
        self,
        *,
        task_name: str,
        goal: str = "",
        interval_seconds: int = LONG_TASK_PROGRESS_INTERVAL_SECONDS,
        poll_seconds: float = _PROGRESS_POLL_SECONDS,
        source: str = LONG_TASK_PROGRESS_SOURCE,
        log_fn: Any = activity.log,
        time_fn: Any = time.monotonic,
        sleep_fn: Any = time.sleep,
    ) -> None:
        self._task_name = task_name
        self._interval_seconds = interval_seconds
        self._poll_seconds = poll_seconds
        self._source = source
        self._log_fn = log_fn
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self._lock = RLock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._progress = LongTaskProgress(task_name=task_name, goal=goal)
        self._last_announced_at = 0.0

    def __enter__(self) -> LongTaskProgressReporter:
        self._last_announced_at = self._time_fn()
        self._thread = Thread(target=self._run, name="long-task-progress", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def update(self, **fields: Any) -> None:
        with self._lock:
            for key, value in fields.items():
                if hasattr(self._progress, key):
                    setattr(self._progress, key, value)

    def snapshot(self) -> LongTaskProgress:
        with self._lock:
            return LongTaskProgress(
                task_name=self._progress.task_name,
                goal=self._progress.goal,
                step=self._progress.step,
                current_file=self._progress.current_file,
                file_index=self._progress.file_index,
                file_count=self._progress.file_count,
                attempt=self._progress.attempt,
                started_at=self._progress.started_at,
            )

    def _run(self) -> None:
        while not self._stop.wait(self._poll_seconds):
            if self._time_fn() - self._last_announced_at < self._interval_seconds:
                continue
            self._announce()
            self._last_announced_at = self._time_fn()

    def _announce(self) -> None:
        announcement = format_progress_update(self.snapshot())
        self._log_fn(
            title=announcement.title,
            detail=announcement.spoken,
            source=self._source,
        )
