import os
import uuid
from typing import Tuple

from fastapi import UploadFile

MEDIA_ROOT = os.getenv("MEDIA_ROOT", "media")


def ensure_media_dirs():
    os.makedirs(MEDIA_ROOT, exist_ok=True)
    os.makedirs(os.path.join(MEDIA_ROOT, "characters"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_ROOT, "scenes"), exist_ok=True)


def save_character_image(character_id: int, file: UploadFile) -> str:
    ensure_media_dirs()
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{character_id}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(MEDIA_ROOT, "characters", filename)

    with open(path, "wb") as f:
        f.write(file.file.read())

    return path


def save_character_image_bytes(character_id: int, image_bytes: bytes, extension: str = ".jpg") -> str:
    """Save character image from bytes (for MCP tool usage)."""
    ensure_media_dirs()
    filename = f"{character_id}_{uuid.uuid4().hex}{extension}"
    path = os.path.join(MEDIA_ROOT, "characters", filename)

    with open(path, "wb") as f:
        f.write(image_bytes)

    return path


def save_scene_image(scene_id: int, file: UploadFile) -> str:
    ensure_media_dirs()
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{scene_id}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(MEDIA_ROOT, "scenes", filename)

    with open(path, "wb") as f:
        f.write(file.file.read())

    return path
