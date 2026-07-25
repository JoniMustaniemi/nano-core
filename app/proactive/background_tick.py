from __future__ import annotations

from datetime import UTC, datetime
from threading import Thread

from app.assistant.pending import pending_interactions
from app.config import get_settings
from app.llm.factory import get_code_llm_client
from app.memory import improvement_plans, internal_notes
from app.memory.internal_note_service import internal_note_service
from app.proactive.codebase_crawl import CodebaseCrawlService
from app.proactive.store import proactive_store
from app.runtime.activity import activity
from app.runtime.user_activity import user_activity
from app.tools.improvement_plan_service import ImprovementPlanService


def run_proactive_background_tick() -> None:
    """Silent internal-note check every 5 min; background plan draft when idle >= 10 min."""
    settings = get_settings()
    conversation_id = settings.proactive_conversation_id

    _ = internal_note_service.list_due_notes()

    if user_activity.is_idle(settings.idle_examine_idle_seconds):
        if (
            settings.idle_examine_enabled
            and not proactive_store.has_offer()
            and not internal_note_service.has_active_plan_pipeline()
            and not proactive_store.is_background_draft_running()
        ):
            pending = pending_interactions.get(conversation_id)
            if pending is None:
                offer = CodebaseCrawlService().scan_next_file(client=get_code_llm_client())
                if offer is not None:
                    internal_note_service.record_from_offer(
                        offer, next_attempt_at=datetime.now(UTC)
                    )

    if not settings.proactive_outreach_enabled:
        return

    if user_activity.seconds_idle() < settings.proactive_outreach_idle_seconds:
        return

    if pending_interactions.get(conversation_id) is not None:
        return

    if proactive_store.has_offer():
        return

    if proactive_store.is_background_draft_running():
        return

    snapshot = activity.snapshot()
    if snapshot.get("state") != "standby":
        return

    if improvement_plans.has_unprocessed_plan():
        return

    due_notes = internal_note_service.list_due_notes()
    note = next(
        (candidate for candidate in due_notes if candidate.kind == "self_improvement_suggestion"),
        None,
    )
    if note is None or note.id is None:
        return

    if not proactive_store.try_start_background_draft():
        return

    thread = Thread(
        target=_run_background_plan_draft,
        args=(note.id,),
        name=f"background-plan-draft-{note.id}",
        daemon=True,
    )
    thread.start()


def _run_background_plan_draft(note_id: int) -> None:
    try:
        note = internal_notes.get_internal_note(note_id)
        if note is None:
            return

        offer = internal_note_service.offer_from_internal_note(note)
        result = ImprovementPlanService().draft_from_note(
            note,
            client=get_code_llm_client(),
            silent=True,
        )
        if result.ok:
            internal_note_service.mark_delivered(note_id)
            goal = str(offer.payload.get("goal", "")).strip()
            if goal:
                raw_files = offer.payload.get("files", [])
                files = (
                    [str(path) for path in raw_files if str(path).strip()]
                    if isinstance(raw_files, list)
                    else []
                )
                proactive_store.set_last_goal(goal, files=files or None)
            return

        internal_note_service.record_deferred_offer(
            offer,
            reason="background_draft_failed",
            note_id=note_id,
        )
    finally:
        proactive_store.finish_background_draft()


def check_presence_timeouts() -> None:
    settings = get_settings()
    conversation_id = settings.proactive_conversation_id
    pending = pending_interactions.get(conversation_id)
    if pending is None or pending.kind != "presence_check":
        return

    from app.assistant.flows.presence_gate import presence_gate

    started_raw = pending.payload.get("presence_started_at")
    if not isinstance(started_raw, str):
        return

    started_at = datetime.fromisoformat(started_raw)
    elapsed = (datetime.now(UTC) - started_at).total_seconds()
    if elapsed >= settings.presence_check_timeout_seconds:
        presence_gate.handle_timeout()
