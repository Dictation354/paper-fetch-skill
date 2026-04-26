"""Image payload detection helpers."""

from __future__ import annotations

from io import BytesIO
from typing import Final

import filetype
import imagesize

_DIMENSION_MIME_TYPES: Final = frozenset(
    {
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


def image_mime_type_from_bytes(body: bytes | bytearray | None) -> str:
    payload = bytes(body or b"")
    if not payload:
        return ""
    kind = filetype.guess(payload)
    if kind is None:
        return ""
    mime_type = str(getattr(kind, "mime", "") or "").lower()
    return mime_type if mime_type.startswith("image/") else ""


def image_dimensions_from_bytes(body: bytes | bytearray | None) -> tuple[int, int] | None:
    payload = bytes(body or b"")
    if not payload or image_mime_type_from_bytes(payload) not in _DIMENSION_MIME_TYPES:
        return None
    try:
        width, height = imagesize.get(BytesIO(payload))
    except Exception:
        return None
    try:
        normalized_width = int(width)
        normalized_height = int(height)
    except (TypeError, ValueError):
        return None
    if normalized_width <= 0 or normalized_height <= 0:
        return None
    return normalized_width, normalized_height
