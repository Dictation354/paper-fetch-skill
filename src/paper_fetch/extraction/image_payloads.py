"""Image payload detection helpers."""

from __future__ import annotations

from io import BytesIO
import re
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

_SVG_DOCUMENT_RE: Final = re.compile(
    r"^(?:<\?xml[^>]*\?>\s*)?(?:<!--.*?-->\s*)*<svg(?:[\s>/]|$)",
    re.IGNORECASE | re.DOTALL,
)


def _looks_like_svg_document(body: bytes | bytearray | None) -> bool:
    if not isinstance(body, (bytes, bytearray)) or not body:
        return False
    prefix = bytes(body[:8192])
    try:
        text = prefix.decode("utf-8-sig", errors="ignore")
    except Exception:
        return False
    normalized = text.lstrip("\ufeff \t\r\n\f")
    if not normalized.startswith(("<", "\ufeff<")):
        return False
    return bool(_SVG_DOCUMENT_RE.match(normalized))


def image_mime_type_from_bytes(body: bytes | bytearray | None) -> str:
    payload = bytes(body or b"")
    if not payload:
        return ""
    kind = filetype.guess(payload)
    if kind is not None:
        mime_type = str(getattr(kind, "mime", "") or "").lower()
        if mime_type.startswith("image/"):
            return mime_type
    return "image/svg+xml" if _looks_like_svg_document(payload) else ""


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
