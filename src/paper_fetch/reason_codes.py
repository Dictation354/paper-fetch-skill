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
IDENTITY_MISMATCH = "identity_mismatch"
AUTH_FINAL_URL_INVALID = "auth_final_url_invalid"
AUTH_REPLAY_FAILED = "auth_replay_failed"
AUTH_STATE_SAVE_FAILED = "auth_state_save_failed"
AUTH_STATE_STAGE_FAILED = "auth_state_stage_failed"
XML_SIZE_EXCEEDED = "xml_size_exceeded"
XML_DEPTH_EXCEEDED = "xml_depth_exceeded"
XML_NODE_LIMIT_EXCEEDED = "xml_node_limit_exceeded"
XML_ENTITIES_FORBIDDEN = "xml_entities_forbidden"
XML_MALFORMED = "xml_malformed"
BROWSER_CONTEXT_CREATE_FAILED = "browser_context_create_failed"
BROWSER_PAGE_CREATE_FAILED = "browser_page_create_failed"
BROWSER_RUNTIME_PREPARE_CANCELLED = "browser_runtime_prepare_cancelled"
BROWSER_RUNTIME_PREPARE_FAILED = "browser_runtime_prepare_failed"
BROWSER_RUNTIME_PREPARE_TIMEOUT = "browser_runtime_prepare_timeout"
BROWSER_RUNTIME_REPAIR_FAILED = "browser_runtime_repair_failed"
CDP_CONNECT_FAILED = "cdp_connect_failed"
MANAGED_CHROME_CDP_TIMEOUT = "managed_chrome_cdp_timeout"
MANAGED_CHROME_EXITED_BEFORE_CDP = "managed_chrome_exited_before_cdp"
MANAGED_CHROME_PROFILE_IN_USE = "managed_chrome_profile_in_use"
BROWSER_RUNTIME_FAILURE_CODES = frozenset(
    {
        BROWSER_CONTEXT_CREATE_FAILED,
        BROWSER_PAGE_CREATE_FAILED,
        BROWSER_RUNTIME_PREPARE_CANCELLED,
        BROWSER_RUNTIME_PREPARE_FAILED,
        BROWSER_RUNTIME_PREPARE_TIMEOUT,
        BROWSER_RUNTIME_REPAIR_FAILED,
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
    "BROWSER_RUNTIME_PREPARE_CANCELLED",
    "BROWSER_RUNTIME_PREPARE_FAILED",
    "BROWSER_RUNTIME_PREPARE_TIMEOUT",
    "BROWSER_RUNTIME_REPAIR_FAILED",
    "CDP_CONNECT_FAILED",
    "ERROR",
    "IDENTITY_MISMATCH",
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
    "XML_DEPTH_EXCEEDED",
    "XML_ENTITIES_FORBIDDEN",
    "XML_MALFORMED",
    "XML_NODE_LIMIT_EXCEEDED",
    "XML_SIZE_EXCEEDED",
]
