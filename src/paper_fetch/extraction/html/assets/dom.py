"""DOM and URL helpers for provider-neutral HTML asset extraction."""

from __future__ import annotations

import urllib.parse
from typing import Any
from collections.abc import Mapping

from ..asset_fields import (
    FULL_SIZE_IMAGE_ATTRS,
    PREVIEW_IMAGE_ATTRS,
    best_url_from_srcset,
)
from ..ui_tokens import SPRINGER_FULL_SIZE_IMAGE_LABEL
from ....models import normalize_text
from ....reason_codes import CLOUDFLARE_CHALLENGE
from ...image_payloads import image_dimensions_from_bytes
from ..signals import (
    CLOUDFLARE_CHALLENGE_TITLE_TOKENS,
    SUPPLEMENTARY_BLOCKING_BODY_TOKENS,
    SUPPLEMENTARY_BLOCKING_TITLE_TOKENS,
)
from ..shared import (
    attr_text,
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
)

from bs4 import Tag

FULL_SIZE_URL_TOKENS = (
    "/full/",
    "/large/",
    "/original/",
    "/fullsize/",
    "download=true",
    "download=1",
    "hi-res",
    "hires",
    "high-res",
    "highres",
)


PREVIEW_URL_TOKENS = ("/thumb/", "/thumbnail/", "thumbnail", "/small/", "/preview/")


ACCEPTABLE_PREVIEW_MIN_WIDTH = 300


ACCEPTABLE_PREVIEW_MIN_HEIGHT = 200


ACCEPTABLE_PREVIEW_MIN_AREA = (
    ACCEPTABLE_PREVIEW_MIN_WIDTH * ACCEPTABLE_PREVIEW_MIN_HEIGHT
)


ACCEPTABLE_WIDE_PREVIEW_MIN_WIDTH = 600


ACCEPTABLE_WIDE_PREVIEW_MIN_HEIGHT = 120


FIGURE_PAGE_HINTS = (
    SPRINGER_FULL_SIZE_IMAGE_LABEL,
    "view figure",
    "open in viewer",
    "view large",
    "view larger",
    "download figure",
    "download image",
    "figure viewer",
)


_CLOUDFLARE_CHALLENGE_TOKENS = CLOUDFLARE_CHALLENGE_TITLE_TOKENS


def _response_dimensions(response: Mapping[str, Any]) -> tuple[int, int] | None:
    dimensions = response.get("dimensions")
    if isinstance(dimensions, Mapping):
        try:
            width = int(dimensions.get("width") or 0)
            height = int(dimensions.get("height") or 0)
        except (TypeError, ValueError):
            width = height = 0
        if width > 0 and height > 0:
            return width, height
    return image_dimensions_from_bytes(response.get("body", b""))


def supplementary_response_block_reason(
    content_type: str | None, body: bytes | bytearray | None
) -> str:
    normalized_content_type = normalize_text(content_type).split(";", 1)[0].lower()
    if normalized_content_type and "html" not in normalized_content_type:
        return ""
    if not isinstance(body, (bytes, bytearray)) or not body:
        return ""
    title = _html_title_snippet(body).lower()
    snippet = _html_text_snippet(body).lower()
    if any(
        token in title or token in snippet for token in _CLOUDFLARE_CHALLENGE_TOKENS
    ):
        return CLOUDFLARE_CHALLENGE
    if any(token in title for token in SUPPLEMENTARY_BLOCKING_TITLE_TOKENS):
        return "login_or_access_html"
    if any(token in snippet for token in SUPPLEMENTARY_BLOCKING_BODY_TOKENS):
        return "login_or_access_html"
    return ""


def preview_dimensions_are_acceptable(width: int | None, height: int | None) -> bool:
    normalized_width = int(width or 0)
    normalized_height = int(height or 0)
    if (
        normalized_width >= ACCEPTABLE_PREVIEW_MIN_WIDTH
        and normalized_height >= ACCEPTABLE_PREVIEW_MIN_HEIGHT
    ):
        return True
    return (
        normalized_width >= ACCEPTABLE_WIDE_PREVIEW_MIN_WIDTH
        and normalized_height >= ACCEPTABLE_WIDE_PREVIEW_MIN_HEIGHT
        and normalized_width * normalized_height >= ACCEPTABLE_PREVIEW_MIN_AREA
    )


def _soup_attr_url(tag: Any, *attrs: str) -> str:
    if not isinstance(tag, Tag):
        return ""
    for attr in attrs:
        raw = tag.get(attr)
        if not raw:
            continue
        if attr.endswith("srcset"):
            candidate = best_url_from_srcset(attr_text(raw))
        else:
            candidate = attr_text(raw)
        if candidate:
            return candidate
    return ""


def looks_like_full_size_asset_url(url: str | None) -> bool:
    candidate = normalize_text(url).lower()
    if not candidate:
        return False
    if any(token in candidate for token in PREVIEW_URL_TOKENS):
        return False
    return any(token in candidate for token in FULL_SIZE_URL_TOKENS)


def _collect_tag_attr_urls(tag: Any, source_url: str, *attrs: str) -> list[str]:
    if not isinstance(tag, Tag):
        return []
    urls: list[str] = []
    for attr in attrs:
        raw = tag.get(attr)
        if not raw:
            continue
        values = [raw] if not isinstance(raw, list) else raw
        for value in values:
            candidate = (
                best_url_from_srcset(attr_text(value))
                if attr.endswith("srcset")
                else attr_text(value)
            )
            absolute_candidate = (
                urllib.parse.urljoin(source_url, candidate) if candidate else ""
            )
            if absolute_candidate and absolute_candidate not in urls:
                urls.append(absolute_candidate)
    return urls


__all__ = [
    "ACCEPTABLE_PREVIEW_MIN_AREA",
    "ACCEPTABLE_PREVIEW_MIN_HEIGHT",
    "ACCEPTABLE_PREVIEW_MIN_WIDTH",
    "ACCEPTABLE_WIDE_PREVIEW_MIN_HEIGHT",
    "ACCEPTABLE_WIDE_PREVIEW_MIN_WIDTH",
    "FIGURE_PAGE_HINTS",
    "FULL_SIZE_IMAGE_ATTRS",
    "FULL_SIZE_URL_TOKENS",
    "PREVIEW_IMAGE_ATTRS",
    "PREVIEW_URL_TOKENS",
    "_collect_tag_attr_urls",
    "_response_dimensions",
    "_soup_attr_url",
    "looks_like_full_size_asset_url",
    "preview_dimensions_are_acceptable",
    "supplementary_response_block_reason",
]
