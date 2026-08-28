"""Shared asset attribute and URL-field vocabularies."""

from __future__ import annotations

import re

from ...utils import normalize_text

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

PREVIEW_IMAGE_ATTRS = ("data-src", "data-image-src", "src", "data-lazy-src")

DEFAULT_ASSET_URL_FIELDS = (
    "url",
    "full_size_url",
    "preview_url",
    "source_url",
    "original_url",
)

MARKDOWN_ASSET_REFERENCE_FIELDS = (
    "path",
    "url",
    "original_url",
    "download_url",
    "source_url",
    "source_path",
    "source_href",
    "preview_url",
    "full_size_url",
    "link",
)


def best_url_from_srcset(value: str | None) -> str:
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
            match = re.match(
                r"^([0-9]+(?:\.[0-9]+)?)(w|x)$", descriptor.strip().lower()
            )
            if not match:
                continue
            multiplier = 1000.0 if match.group(2) == "x" else 1.0
            score = max(score, float(match.group(1)) * multiplier)
        if score >= best_score:
            best_url = url
            best_score = score
    return best_url


__all__ = [
    "DEFAULT_ASSET_URL_FIELDS",
    "FULL_SIZE_IMAGE_ATTRS",
    "MARKDOWN_ASSET_REFERENCE_FIELDS",
    "PREVIEW_IMAGE_ATTRS",
    "best_url_from_srcset",
]
