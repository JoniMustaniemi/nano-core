from datetime import UTC, datetime

from app.common.types import ProactiveOffer


def test_proactive_offer_from_json_handles_malformed_root() -> None:
    offer = ProactiveOffer.from_json("[]")

    assert offer.kind == ""
    assert offer.title == ""
    assert offer.summary == ""
    assert offer.payload == {}
    assert offer.created_at.tzinfo is UTC


def test_proactive_offer_from_json_handles_invalid_created_at_and_payload() -> None:
    offer = ProactiveOffer.from_json(
        '{"kind":"note","title":"Timers","summary":"Fix copy","created_at":"not-a-date","payload":["bad"]}'
    )

    assert offer.kind == "note"
    assert offer.title == "Timers"
    assert offer.summary == "Fix copy"
    assert offer.payload == {}
    assert offer.created_at.tzinfo is UTC


def test_proactive_offer_from_json_normalizes_naive_created_at() -> None:
    offer = ProactiveOffer.from_json(
        '{"kind":"note","title":"Timers","summary":"Fix copy","created_at":"2026-01-02T03:04:05","payload":{}}'
    )

    assert offer.created_at == datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
