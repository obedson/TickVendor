"""Image upload validation tests."""

import io

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from src.uploads import safe_upload_name, validate_image_upload


@pytest.mark.anyio
async def test_validates_magic_bytes_and_safe_name():
    upload = UploadFile(
        io.BytesIO(b"\x89PNG\r\n\x1a\ncontent"),
        filename="../bad name.png",
        headers=Headers({"content-type": "image/png"}),
    )
    assert await validate_image_upload(upload)
    name = safe_upload_name("user", upload.filename, upload.content_type)
    assert ".." not in name
    assert "/" not in name


@pytest.mark.anyio
async def test_rejects_spoofed_image():
    upload = UploadFile(
        io.BytesIO(b"not an image"),
        filename="fake.png",
        headers=Headers({"content-type": "image/png"}),
    )
    with pytest.raises(HTTPException) as invalid:
        await validate_image_upload(upload)
    assert invalid.value.status_code == 422
