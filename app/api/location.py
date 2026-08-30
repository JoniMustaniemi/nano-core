from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.runtime.location import location_store

router = APIRouter(prefix="/location", tags=["location"])


class LocationUpdateRequest(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    accuracy_m: float | None = Field(default=None, ge=0.0)


class LocationResponse(BaseModel):
    latitude: float
    longitude: float
    accuracy_m: float | None = None
    updated_at: str | None = None
    source: str | None = None


@router.get("")
def get_location() -> LocationResponse:
    """Return the current client-reported location."""
    snapshot = location_store.snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Location has not been reported yet.")
    return LocationResponse(**snapshot)


@router.post("")
def update_location(body: LocationUpdateRequest) -> LocationResponse:
    """Store location reported by the web UI (browser geolocation)."""
    snapshot = location_store.update(
        body.latitude,
        body.longitude,
        accuracy_m=body.accuracy_m,
        source="browser",
    )
    return LocationResponse(**snapshot)
