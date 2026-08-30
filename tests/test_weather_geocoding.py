from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.integrations.weather.geocoding import resolve_place_name


def test_resolve_place_name_prefers_city(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "city": "Helsinki",
        "locality": "Helsinki",
        "principalSubdivision": "Uusimaa",
    }
    monkeypatch.setattr(
        "app.integrations.weather.geocoding.httpx.get",
        lambda *args, **kwargs: response,
    )

    assert resolve_place_name(60.17, 24.94) == "Helsinki"


def test_resolve_place_name_falls_back_to_locality(monkeypatch: pytest.MonkeyPatch) -> None:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "locality": "Espoo",
        "principalSubdivision": "Uusimaa",
    }
    monkeypatch.setattr(
        "app.integrations.weather.geocoding.httpx.get",
        lambda *args, **kwargs: response,
    )

    assert resolve_place_name(60.2, 24.65) == "Espoo"


def test_resolve_place_name_returns_none_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    def raise_error(*args, **kwargs):
        raise httpx.HTTPError("network down")

    monkeypatch.setattr("app.integrations.weather.geocoding.httpx.get", raise_error)

    assert resolve_place_name(60.17, 24.94) is None
