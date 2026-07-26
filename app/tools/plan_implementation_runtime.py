from __future__ import annotations

import threading
from uuid import uuid4

_workers_lock = threading.Lock()
_workers: dict[int, threading.Thread] = {}
_cancel_events: dict[int, threading.Event] = {}
_DEFAULT_CANCEL_TIMEOUT_SECONDS = 30.0


def issue_implementing_lease() -> str:
    return uuid4().hex


def register_worker(plan_id: int, thread: threading.Thread) -> threading.Event:
    cancel_event = threading.Event()
    with _workers_lock:
        _workers[plan_id] = thread
        _cancel_events[plan_id] = cancel_event
    return cancel_event


def unregister_worker(plan_id: int) -> None:
    with _workers_lock:
        _workers.pop(plan_id, None)
        _cancel_events.pop(plan_id, None)


def is_worker_live(plan_id: int) -> bool:
    with _workers_lock:
        thread = _workers.get(plan_id)
    return thread is not None and thread.is_alive()


def cancel_and_wait(
    plan_id: int,
    *,
    timeout: float = _DEFAULT_CANCEL_TIMEOUT_SECONDS,
) -> bool:
    with _workers_lock:
        cancel_event = _cancel_events.get(plan_id)
        thread = _workers.get(plan_id)
    if cancel_event is not None:
        cancel_event.set()
    if thread is None:
        return True
    thread.join(timeout=timeout)
    return not thread.is_alive()


def is_cancelled(*, cancel_event: threading.Event | None) -> bool:
    return cancel_event is not None and cancel_event.is_set()
