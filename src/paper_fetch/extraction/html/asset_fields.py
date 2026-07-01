"""Shared asset attribute and URL-field vocabularies."""

from __future__ import annotations

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


__all__ = [
    "DEFAULT_ASSET_URL_FIELDS",
    "FULL_SIZE_IMAGE_ATTRS",
    "PREVIEW_IMAGE_ATTRS",
]
