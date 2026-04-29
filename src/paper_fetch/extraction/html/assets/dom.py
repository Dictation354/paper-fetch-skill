"""DOM and URL helpers for provider-neutral HTML asset extraction."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Mapping

from ....models import normalize_text
from ...image_payloads import image_dimensions_from_bytes
from ..shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
)

try:
    from bs4 import Tag
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    Tag = None

FULL_SIZE_IMAGE_ATTRS = (
    "data-original",
    "data-full-size",
    "data-fullsize",
    "data-zoom-src",
    "data-zoom-image",
    "data-lg-src",
    "data-hi-res-src",
    "data-hires",
    "data-large-src",
    "data-image-full",
    "data-download-url",
)


PREVIEW_IMAGE_ATTRS = ("data-src", "src", "data-lazy-src")


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


FIGURE_PAGE_HINTS = (
    "full size image",
    "view figure",
    "open in viewer",
    "view larger",
    "download figure",
    "download image",
    "figure viewer",
)


_CLOUDFLARE_CHALLENGE_TOKENS = (
    "just a moment",
    "attention required",
    "checking your browser",
)


SUPPLEMENTARY_BLOCKING_TITLE_TOKENS = (
    "just a moment",
    "attention required",
    "checking your browser",
    "sign in",
    "sign-in",
    "login",
    "log in",
    "access denied",
)


SUPPLEMENTARY_BLOCKING_BODY_TOKENS = (
    "checking your browser",
    "enable javascript and cookies",
    "cloudflare",
    "please sign in",
    "institutional login",
    "access denied",
)


def _response_header(response: Mapping[str, Any], name: str) -> str:
    headers = response.get("headers") or {}
    if not isinstance(headers, Mapping):
        return ""
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered:
            return normalize_text(str(value or ""))
    return ""


def _image_dimensions(body: bytes | bytearray | None) -> tuple[int, int] | None:
    return image_dimensions_from_bytes(body)


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
    return _image_dimensions(response.get("body", b""))


def supplementary_response_block_reason(content_type: str | None, body: bytes | bytearray | None) -> str:
    normalized_content_type = normalize_text(content_type).split(";", 1)[0].lower()
    if normalized_content_type and "html" not in normalized_content_type:
        return ""
    if not isinstance(body, (bytes, bytearray)) or not body:
        return ""
    title = _html_title_snippet(body).lower()
    snippet = _html_text_snippet(body).lower()
    if any(token in title or token in snippet for token in _CLOUDFLARE_CHALLENGE_TOKENS):
        return "cloudflare_challenge"
    if any(token in title for token in SUPPLEMENTARY_BLOCKING_TITLE_TOKENS):
        return "login_or_access_html"
    if any(token in snippet for token in SUPPLEMENTARY_BLOCKING_BODY_TOKENS):
        return "login_or_access_html"
    return ""


def preview_dimensions_are_acceptable(width: int | None, height: int | None) -> bool:
    return int(width or 0) >= ACCEPTABLE_PREVIEW_MIN_WIDTH and int(height or 0) >= ACCEPTABLE_PREVIEW_MIN_HEIGHT


def _first_url_from_srcset(value: str | None) -> str:
    srcset = normalize_text(value)
    if not srcset:
        return ""
    best_url = ""
    best_score = -1.0
    for raw_part in srcset.split(","):
        part = raw_part.strip()
        if not part:
            continue
        pieces = part.split()
        url = pieces[0].strip()
        score = 0.0
        for descriptor in pieces[1:]:
            match = re.match(r"^([0-9]+(?:\.[0-9]+)?)(w|x)$", descriptor.strip().lower())
            if not match:
                continue
            multiplier = 1000.0 if match.group(2) == "x" else 1.0
            score = max(score, float(match.group(1)) * multiplier)
        if score >= best_score:
            best_url = url
            best_score = score
    return best_url


def _soup_attr_url(tag: Any, *attrs: str) -> str:
    if Tag is None or not isinstance(tag, Tag):
        return ""
    for attr in attrs:
        raw = tag.get(attr)
        if not raw:
            continue
        if attr.endswith("srcset"):
            candidate = _first_url_from_srcset(raw)
        else:
            candidate = normalize_text(str(raw))
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
    if Tag is None or not isinstance(tag, Tag):
        return []
    urls: list[str] = []
    for attr in attrs:
        raw = tag.get(attr)
        if not raw:
            continue
        values = [raw] if not isinstance(raw, list) else raw
        for value in values:
            candidate = _first_url_from_srcset(value) if attr.endswith("srcset") else normalize_text(str(value))
            absolute_candidate = urllib.parse.urljoin(source_url, candidate) if candidate else ""
            if absolute_candidate and absolute_candidate not in urls:
                urls.append(absolute_candidate)
    return urls


__all__ = [
    "FULL_SIZE_IMAGE_ATTRS",
    "PREVIEW_IMAGE_ATTRS",
    "FULL_SIZE_URL_TOKENS",
    "PREVIEW_URL_TOKENS",
    "ACCEPTABLE_PREVIEW_MIN_WIDTH",
    "ACCEPTABLE_PREVIEW_MIN_HEIGHT",
    "FIGURE_PAGE_HINTS",
    "_response_header",
    "_image_dimensions",
    "_response_dimensions",
    "supplementary_response_block_reason",
    "preview_dimensions_are_acceptable",
    "_first_url_from_srcset",
    "_soup_attr_url",
    "looks_like_full_size_asset_url",
    "_collect_tag_attr_urls",
]
