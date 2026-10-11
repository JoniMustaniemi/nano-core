from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from googleapiclient.errors import HttpError
from pydantic import BaseModel

from app.integrations.google_drive import (
    GoogleDriveAccessError,
    GoogleDriveAuthenticationError,
    GoogleDriveBinaryNotSupportedError,
    GoogleDriveNotFoundError,
    get_file_metadata,
    read_file_content,
)

router = APIRouter(prefix="/drive", tags=["drive"])


class DriveFileMetadataResponse(BaseModel):
    id: str
    name: str
    mime_type: str
    size: int | None = None


@router.get("/files/{file_id}", response_model=DriveFileMetadataResponse)
def read_drive_file_metadata(file_id: str) -> DriveFileMetadataResponse:
    try:
        metadata = get_file_metadata(file_id)
    except GoogleDriveAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GoogleDriveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GoogleDriveAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except HttpError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Google Drive API request failed: {exc}",
        ) from exc

    size = metadata.get("size")
    return DriveFileMetadataResponse(
        id=str(metadata.get("id") or file_id),
        name=str(metadata.get("name") or ""),
        mime_type=str(metadata.get("mimeType") or ""),
        size=int(size) if isinstance(size, int) else None,
    )


@router.get("/files/{file_id}/content")
def read_drive_file_content(file_id: str) -> Response:
    try:
        name, content, truncated = read_file_content(file_id)
    except GoogleDriveAuthenticationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GoogleDriveNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GoogleDriveAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GoogleDriveBinaryNotSupportedError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except HttpError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Google Drive API request failed: {exc}",
        ) from exc

    headers: dict[str, str] = {}
    if truncated:
        headers["X-Content-Truncated"] = "true"
    headers["X-File-Name"] = name
    return Response(content=content, media_type="text/plain; charset=utf-8", headers=headers)
