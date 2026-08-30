from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock


@dataclass
class LocationState:
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None
    updated_at: datetime | None = None
    source: str | None = None
    place_name: str | None = None


class LocationStore:
    """In-memory store for the current client-reported geographic location."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = LocationState()

    def update(
        self,
        latitude: float,
        longitude: float,
        *,
        accuracy_m: float | None = None,
        source: str = "browser",
    ) -> dict[str, object]:
        from app.integrations.weather.geocoding import resolve_place_name

        with self._lock:
            coordinates_changed = (
                self._state.latitude != latitude or self._state.longitude != longitude
            )
            self._state.latitude = latitude
            self._state.longitude = longitude
            self._state.accuracy_m = accuracy_m
            self._state.updated_at = datetime.now(UTC)
            self._state.source = source
            if coordinates_changed or not self._state.place_name:
                self._state.place_name = resolve_place_name(latitude, longitude)
            return self._snapshot_unlocked()

    def has_location(self) -> bool:
        with self._lock:
            return self._state.latitude is not None and self._state.longitude is not None

    def get_coordinates(self) -> tuple[float, float] | None:
        with self._lock:
            if self._state.latitude is None or self._state.longitude is None:
                return None
            return self._state.latitude, self._state.longitude

    def get_place_name(self) -> str | None:
        with self._lock:
            return self._state.place_name

    def snapshot(self) -> dict[str, object] | None:
        with self._lock:
            if self._state.latitude is None or self._state.longitude is None:
                return None
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> dict[str, object]:
        updated_at = self._state.updated_at
        return {
            "latitude": self._state.latitude,
            "longitude": self._state.longitude,
            "accuracy_m": self._state.accuracy_m,
            "updated_at": updated_at.isoformat() if updated_at is not None else None,
            "source": self._state.source,
            "place_name": self._state.place_name,
        }

    def reset(self) -> None:
        with self._lock:
            self._state = LocationState()


location_store = LocationStore()
