"""Compatibility re-exports for browser workflow fetchers."""

from __future__ import annotations

from .browser_workflow_fetchers.context import (
    _BasePlaywrightDocumentFetcher,
    _choose_playwright_seed_url,
    _looks_like_pdf_navigation_url,
    _new_playwright_context,
    _normalized_response_headers,
)
from .browser_workflow_fetchers.diagnostics import (
    _CLOUDFLARE_CHALLENGE_TITLE_TOKENS,
    _compact_failure_diagnostic,
    _copy_failure_diagnostic,
    _flaresolverr_image_payload_failure_reason,
    _image_fetch_failure_reason,
    _is_timeout_error,
    _looks_like_cloudflare_challenge_failure,
    _looks_like_cloudflare_challenge_title,
)
from .browser_workflow_fetchers.file import (
    _SharedPlaywrightFileDocumentFetcher,
    _ThreadLocalSharedPlaywrightFileDocumentFetcher,
    _build_shared_playwright_file_fetcher,
)
from .browser_workflow_fetchers.image import (
    _IMAGE_DOCUMENT_FETCH_TIMEOUT_MS,
    _SharedPlaywrightImageDocumentFetcher,
    _ThreadLocalSharedPlaywrightImageDocumentFetcher,
    _build_shared_playwright_image_fetcher,
    _copy_image_payload,
    _decode_base64_bytes,
    _flaresolverr_image_document_payload,
    fetch_image_document_with_playwright,
    _looks_like_image_response_payload,
    _normalized_recovered_image_payload,
    _payload_from_flaresolverr_image_payload,
)
from .browser_workflow_fetchers.memo import (
    _MemoizedFigurePageFetcher,
    _MemoizedImageDocumentFetcher,
)
from .browser_workflow_fetchers.scripts import _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT

__all__ = [
    "_CLOUDFLARE_CHALLENGE_TITLE_TOKENS",
    "_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS",
    "_LOADED_IMAGE_CANVAS_EXPORT_SCRIPT",
    "_BasePlaywrightDocumentFetcher",
    "_MemoizedFigurePageFetcher",
    "_MemoizedImageDocumentFetcher",
    "_SharedPlaywrightFileDocumentFetcher",
    "_SharedPlaywrightImageDocumentFetcher",
    "_ThreadLocalSharedPlaywrightFileDocumentFetcher",
    "_ThreadLocalSharedPlaywrightImageDocumentFetcher",
    "_build_shared_playwright_file_fetcher",
    "_build_shared_playwright_image_fetcher",
    "_choose_playwright_seed_url",
    "_compact_failure_diagnostic",
    "_copy_failure_diagnostic",
    "_copy_image_payload",
    "_decode_base64_bytes",
    "_flaresolverr_image_document_payload",
    "_flaresolverr_image_payload_failure_reason",
    "_image_fetch_failure_reason",
    "_is_timeout_error",
    "_looks_like_cloudflare_challenge_failure",
    "_looks_like_cloudflare_challenge_title",
    "_looks_like_image_response_payload",
    "_looks_like_pdf_navigation_url",
    "_new_playwright_context",
    "_normalized_recovered_image_payload",
    "_normalized_response_headers",
    "_payload_from_flaresolverr_image_payload",
    "fetch_image_document_with_playwright",
]
