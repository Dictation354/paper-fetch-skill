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

ABSTRACT_ONLY = "abstract_only"
METADATA_ONLY = "metadata_only"
PDF_FALLBACK = "pdf_fallback"

OK = "ok"
PARTIAL = "partial"
READY = "ready"


__all__ = [
    "ABSTRACT_ONLY",
    "ERROR",
    "IMAGE_CONVERSION_BACKEND_ERROR",
    "IMAGE_CONVERSION_BACKEND_MISSING",
    "IMAGE_CONVERSION_BACKEND_READY",
    "IMAGE_CONVERSION_BACKEND_TIMEOUT",
    "IMAGE_CONVERSION_FAILED",
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
