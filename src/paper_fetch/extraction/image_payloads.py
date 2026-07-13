"""Image payload detection helpers."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Any, Final
import urllib.parse

import filetype
import imagesize

_PAYLOAD_INSPECTION_BYTES: Final = 8192
_PLACEHOLDER_IMAGE_BASENAMES: Final = frozenset({"blank.svg", "blank.png", "blank.gif"})

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


def payload_mime_type_from_bytes(body: bytes | bytearray | None) -> str:
    """Return the file-signature MIME type without trusting names or headers."""

    payload = bytes(body or b"")
    if not payload:
        return ""
    kind = filetype.guess(payload)
    if kind is not None:
        mime_type = str(getattr(kind, "mime", "") or "").lower()
        if mime_type:
            return mime_type
    return "image/svg+xml" if _looks_like_svg_document(payload) else ""


def payload_mime_type_from_path(path: str | Path) -> str:
    try:
        with Path(path).open("rb") as handle:
            return payload_mime_type_from_bytes(handle.read(_PAYLOAD_INSPECTION_BYTES))
    except OSError:
        return ""


def image_mime_type_from_bytes(body: bytes | bytearray | None) -> str:
    mime_type = payload_mime_type_from_bytes(body)
    return mime_type if mime_type.startswith("image/") else ""


def _normalize_dimensions(width: Any, height: Any) -> tuple[int, int] | None:
    try:
        normalized_width = int(width)
        normalized_height = int(height)
    except (TypeError, ValueError):
        return None
    if normalized_width <= 0 or normalized_height <= 0:
        return None
    return normalized_width, normalized_height


def image_dimensions_from_bytes(
    body: bytes | bytearray | None,
) -> tuple[int, int] | None:
    payload = bytes(body or b"")
    if not payload or not image_mime_type_from_bytes(payload):
        return None
    try:
        width, height = imagesize.get(BytesIO(payload))
    except Exception:
        return None
    return _normalize_dimensions(width, height)


def image_dimensions_from_path(path: str | Path) -> tuple[int, int] | None:
    if not payload_mime_type_from_path(path).startswith("image/"):
        return None
    try:
        width, height = imagesize.get(str(path))
    except Exception:
        return None
    return _normalize_dimensions(width, height)


def is_placeholder_image_url(value: str | None) -> bool:
    normalized = str(value or "").strip()
    if not normalized:
        return False
    path = urllib.parse.unquote(urllib.parse.urlparse(normalized).path).lower()
    return path.rsplit("/", 1)[-1] in _PLACEHOLDER_IMAGE_BASENAMES
