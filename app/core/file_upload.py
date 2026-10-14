from __future__ import annotations

import os
import asyncio
import io
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.util.concurrency import await_only, in_greenlet


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
    if in_greenlet():
        return await_only(asyncio.to_thread(_validate_and_normalize_image, file, max_size_mb))
    return _validate_and_normalize_image(file, max_size_mb)


def _validate_and_normalize_image(file: UploadFile, max_size_mb: int) -> tuple[str, int]:
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

    # Полное декодирование отклоняет подделки; перекодирование удаляет метаданные и хвост файла.
    file.file.seek(0)
    try:
        with Image.open(file.file, formats=["JPEG", "PNG", "WEBP"]) as image:
            if image.width * image.height > 20_000_000:
                raise HTTPException(status_code=400, detail="Изображение должно содержать не более 20 мегапикселей")
            image.load()
            normalized = ImageOps.exif_transpose(image)
            output = io.BytesIO()
            ext = "png" if image.format == "PNG" else "jpg"
            normalized = normalized.convert("RGBA" if ext == "png" else "RGB")
            normalized.info.clear()
            normalized.save(output, format="PNG" if ext == "png" else "JPEG", quality=90)
            data = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="Файл не является допустимым изображением") from exc
    if len(data) > max_size_bytes:
        raise HTTPException(status_code=400, detail=f"Изображение после обработки превышает {max_size_mb} МБ")
    file.file.seek(0)
    file.file.truncate()
    file.file.write(data)
    file.file.seek(0)
    return ext, len(data)
