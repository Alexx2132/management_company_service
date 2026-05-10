from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, UploadFile


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
DEFAULT_MAX_IMAGE_SIZE_MB = 8


def _get_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        raise HTTPException(status_code=400, detail="File extension is required")
    return Path(filename).suffix.lower().lstrip(".")


def validate_image_upload(file: UploadFile, max_size_mb: int = DEFAULT_MAX_IMAGE_SIZE_MB) -> tuple[str, int]:
    if file is None:
        raise HTTPException(status_code=400, detail="File is required")

    ext = _get_extension(file.filename)
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension: .{ext}. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
        )

    content_type = (file.content_type or "").lower().strip()
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type: {content_type}",
        )

    current_pos = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    size_bytes = file.file.tell()
    file.file.seek(current_pos)

    if size_bytes <= 0:
        raise HTTPException(status_code=400, detail="Empty file")

    max_size_bytes = max_size_mb * 1024 * 1024
    if size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File is too large. Max size is {max_size_mb} MB",
        )

    return ext, size_bytes