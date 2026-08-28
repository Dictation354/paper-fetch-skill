"""Shared failure, status, and route/content-kind reason codes."""

from __future__ import annotations

NO_RESULT = "no_result"
NO_ACCESS = "no_access"
NOT_CONFIGURED = "not_configured"
NOT_SUPPORTED = "not_supported"
RATE_LIMITED = "rate_limited"
ERROR = "error"
ASSET_BYTES_PER_ASSET_EXCEEDED = "asset_bytes_per_asset_exceeded"
ASSET_BYTES_TOTAL_EXCEEDED = "asset_bytes_total_exceeded"
ASSET_CANCELLED = "asset_cancelled"
ASSET_CONTENT_ENCODING_UNSUPPORTED = "asset_content_encoding_unsupported"
ASSET_FILE_LIMIT_EXCEEDED = "asset_file_limit_exceeded"
ASSET_PIXEL_LIMIT_EXCEEDED = "asset_pixel_limit_exceeded"
BROWSER_STREAM_UNAVAILABLE = "browser_stream_unavailable"
IMAGE_CONVERSION_BACKEND_ERROR = "image_conversion_backend_error"
IMAGE_CONVERSION_BACKEND_MISSING = "image_conversion_backend_missing"
IMAGE_CONVERSION_BACKEND_READY = "image_conversion_backend_ready"
IMAGE_CONVERSION_BACKEND_TIMEOUT = "image_conversion_backend_timeout"
IMAGE_CONVERSION_FAILED = "image_conversion_failed"
OFFICIAL_FULL_SIZE_ACCESS_RESTRICTED = "official_full_size_access_restricted"
OFFICIAL_FULL_SIZE_NOT_EXPOSED = "official_full_size_not_exposed"
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
CLOUDFLARE_CHALLENGE = "cloudflare_challenge"
AWS_WAF_CHALLENGE = "aws_waf_challenge"
PUBLISHER_NOT_FOUND = "publisher_not_found"
PUBLISHER_ACCESS_DENIED = "publisher_access_denied"
PUBLISHER_PAYWALL = "publisher_paywall"
REDIRECTED_TO_ABSTRACT = "redirected_to_abstract"
FULLTEXT = "fulltext"
BODY_SUFFICIENT = "body_sufficient"
INSUFFICIENT_BODY = "insufficient_body"
EMPTY_ARTICLE_SHELL = "empty_article_shell"
STRUCTURED_ARTICLE_NOT_FULLTEXT = "structured_article_not_fulltext"
STRUCTURED_MISSING_BODY_SECTIONS = "structured_missing_body_sections"
ACCESS_PAGE_URL = "access_page_url"
FINAL_URL_MATCHES_CITATION_ABSTRACT_HTML_URL = (
    "final_url_matches_citation_abstract_html_url"
)
DATA_ARTICLE_ACCESS_ABSTRACT = "data_article_access_abstract"
DATA_ARTICLE_ACCESS_NO = "data_article_access_no"
WT_ABSTRACT_PAGE_TYPE = "wt_abstract_page_type"
CITATION_ABSTRACT_HTML_URL = "citation_abstract_html_url"

OK = "ok"
PARTIAL = "partial"
READY = "ready"


__all__ = [
    "ABSTRACT_ONLY",
    "ACCESS_PAGE_URL",
    "ASSET_BYTES_PER_ASSET_EXCEEDED",
    "ASSET_BYTES_TOTAL_EXCEEDED",
    "ASSET_CANCELLED",
    "ASSET_CONTENT_ENCODING_UNSUPPORTED",
    "ASSET_FILE_LIMIT_EXCEEDED",
    "ASSET_PIXEL_LIMIT_EXCEEDED",
    "AWS_WAF_CHALLENGE",
    "BODY_SUFFICIENT",
    "BROWSER_CONTEXT_CREATE_FAILED",
    "BROWSER_PAGE_CREATE_FAILED",
    "BROWSER_RUNTIME_FAILURE_CODES",
    "BROWSER_RUNTIME_PREPARE_CANCELLED",
    "BROWSER_RUNTIME_PREPARE_FAILED",
    "BROWSER_RUNTIME_PREPARE_TIMEOUT",
    "BROWSER_RUNTIME_REPAIR_FAILED",
    "BROWSER_STREAM_UNAVAILABLE",
    "CDP_CONNECT_FAILED",
    "CITATION_ABSTRACT_HTML_URL",
    "CLOUDFLARE_CHALLENGE",
    "DATA_ARTICLE_ACCESS_ABSTRACT",
    "DATA_ARTICLE_ACCESS_NO",
    "EMPTY_ARTICLE_SHELL",
    "ERROR",
    "FINAL_URL_MATCHES_CITATION_ABSTRACT_HTML_URL",
    "FULLTEXT",
    "IDENTITY_MISMATCH",
    "IMAGE_CONVERSION_BACKEND_ERROR",
    "IMAGE_CONVERSION_BACKEND_MISSING",
    "IMAGE_CONVERSION_BACKEND_READY",
    "IMAGE_CONVERSION_BACKEND_TIMEOUT",
    "IMAGE_CONVERSION_FAILED",
    "INSUFFICIENT_BODY",
    "MANAGED_CHROME_CDP_TIMEOUT",
    "MANAGED_CHROME_EXITED_BEFORE_CDP",
    "MANAGED_CHROME_PROFILE_IN_USE",
    "METADATA_ONLY",
    "NOT_CONFIGURED",
    "NOT_SUPPORTED",
    "NO_ACCESS",
    "NO_RESULT",
    "OFFICIAL_FULL_SIZE_ACCESS_RESTRICTED",
    "OFFICIAL_FULL_SIZE_NOT_EXPOSED",
    "OK",
    "PARTIAL",
    "PDF_FALLBACK",
    "PUBLISHER_ACCESS_DENIED",
    "PUBLISHER_NOT_FOUND",
    "PUBLISHER_PAYWALL",
    "RATE_LIMITED",
    "READY",
    "REDIRECTED_TO_ABSTRACT",
    "STRUCTURED_ARTICLE_NOT_FULLTEXT",
    "STRUCTURED_MISSING_BODY_SECTIONS",
    "WT_ABSTRACT_PAGE_TYPE",
    "XML_DEPTH_EXCEEDED",
    "XML_ENTITIES_FORBIDDEN",
    "XML_MALFORMED",
    "XML_NODE_LIMIT_EXCEEDED",
    "XML_SIZE_EXCEEDED",
]
