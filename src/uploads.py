"""File and image upload validation helpers."""

from pathlib import Path

from fastapi import HTTPException, UploadFile

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAGIC_BYTES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


async def validate_image_upload(upload: UploadFile) -> bytes:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported image type")
    data = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 5 MB")
    if not any(data.startswith(prefix) for prefix in MAGIC_BYTES[upload.content_type]):
        raise HTTPException(status_code=422, detail="Image content does not match type")
    if upload.content_type == "image/webp" and data[8:12] != b"WEBP":
        raise HTTPException(status_code=422, detail="Invalid WebP image")
    return data


def safe_upload_name(user_id: str, original_name: str | None, content_type: str) -> str:
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]
    stem = Path(original_name or "upload").stem[:30]
    sanitized = "".join(character for character in stem if character.isalnum() or character in "-_")
    return f"{user_id}-{sanitized or 'upload'}{extension}"
