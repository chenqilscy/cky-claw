"""媒体上传 API 路由。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.deps import require_permission
from app.schemas.media import MediaUploadResponse

router = APIRouter(prefix="/api/v1/media", tags=["media"])

_UPLOAD_DIR = Path("uploads") / "media"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(filename: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    return safe[:200] or "file.bin"


@router.post(
    "/upload",
    response_model=MediaUploadResponse,
    status_code=201,
    dependencies=[Depends(require_permission("sessions", "write"))],
)
async def upload_media(file: UploadFile = File(...)) -> MediaUploadResponse:
    """上传多模态媒体文件。"""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件不可上传")

    original = file.filename or "file.bin"
    safe_name = _sanitize_filename(original)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    target = _UPLOAD_DIR / stored_name
    target.write_bytes(raw)

    return MediaUploadResponse(
        url=f"/api/v1/media/{stored_name}",
        filename=original,
        media_type=file.content_type or "application/octet-stream",
        size_bytes=len(raw),
    )


@router.get("/{stored_name}")
async def get_media(stored_name: str) -> FileResponse:
    """下载媒体文件。"""
    if "/" in stored_name or "\\" in stored_name:
        raise HTTPException(status_code=400, detail="非法文件名")

    target = _UPLOAD_DIR / stored_name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(target)
