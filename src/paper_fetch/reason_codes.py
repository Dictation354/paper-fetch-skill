"""Shared failure, status, and route/content-kind reason codes."""

from __future__ import annotations

NO_RESULT = "no_result"
NO_ACCESS = "no_access"
NOT_CONFIGURED = "not_configured"
NOT_SUPPORTED = "not_supported"
RATE_LIMITED = "rate_limited"
ERROR = "error"
IMAGE_CONVERSION_BACKEND_ERROR = "image_conversion_backend_error"
IMAGE_CONVERSION_BACKEND_MISSING = "image_conversion_backend_missing"
IMAGE_CONVERSION_BACKEND_READY = "image_conversion_backend_ready"
IMAGE_CONVERSION_BACKEND_TIMEOUT = "image_conversion_backend_timeout"
IMAGE_CONVERSION_FAILED = "image_conversion_failed"
BROWSER_CONTEXT_CREATE_FAILED = "browser_context_create_failed"
BROWSER_PAGE_CREATE_FAILED = "browser_page_create_failed"
CDP_CONNECT_FAILED = "cdp_connect_failed"
MANAGED_CHROME_CDP_TIMEOUT = "managed_chrome_cdp_timeout"
MANAGED_CHROME_EXITED_BEFORE_CDP = "managed_chrome_exited_before_cdp"
MANAGED_CHROME_PROFILE_IN_USE = "managed_chrome_profile_in_use"
BROWSER_RUNTIME_FAILURE_CODES = frozenset(
    {
        BROWSER_CONTEXT_CREATE_FAILED,
        BROWSER_PAGE_CREATE_FAILED,
        CDP_CONNECT_FAILED,
        MANAGED_CHROME_CDP_TIMEOUT,
        MANAGED_CHROME_EXITED_BEFORE_CDP,
        MANAGED_CHROME_PROFILE_IN_USE,
    }
)

ABSTRACT_ONLY = "abstract_only"
METADATA_ONLY = "metadata_only"
PDF_FALLBACK = "pdf_fallback"

OK = "ok"
PARTIAL = "partial"
READY = "ready"


__all__ = [
    "ABSTRACT_ONLY",
    "BROWSER_CONTEXT_CREATE_FAILED",
    "BROWSER_PAGE_CREATE_FAILED",
    "BROWSER_RUNTIME_FAILURE_CODES",
    "CDP_CONNECT_FAILED",
    "ERROR",
    "IMAGE_CONVERSION_BACKEND_ERROR",
    "IMAGE_CONVERSION_BACKEND_MISSING",
    "IMAGE_CONVERSION_BACKEND_READY",
    "IMAGE_CONVERSION_BACKEND_TIMEOUT",
    "IMAGE_CONVERSION_FAILED",
    "MANAGED_CHROME_CDP_TIMEOUT",
    "MANAGED_CHROME_EXITED_BEFORE_CDP",
    "MANAGED_CHROME_PROFILE_IN_USE",
    "METADATA_ONLY",
    "NOT_CONFIGURED",
    "NOT_SUPPORTED",
    "NO_ACCESS",
    "NO_RESULT",
    "OK",
    "PARTIAL",
    "PDF_FALLBACK",
    "RATE_LIMITED",
    "READY",
]
