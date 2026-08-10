"""Shared browser-workflow runtime helpers for provider browser routes."""

from __future__ import annotations

from importlib import import_module
import time as time
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "BrowserWorkflowBootstrapResult": (".profile", "BrowserWorkflowBootstrapResult"),
    "BrowserWorkflowPolicy": (".profile", "BrowserWorkflowPolicy"),
    "BrowserWorkflowClient": (".client", "BrowserWorkflowClient"),
    "PdfFallbackFailure": ("paper_fetch.providers._pdf_fallback", "PdfFallbackFailure"),
    "ProviderBrowserProfile": (".profile", "ProviderBrowserProfile"),
    "browser_profile_catalog_mismatches": (
        ".profile",
        "browser_profile_catalog_mismatches",
    ),
    "make_browser_profile": (".profile", "make_browser_profile"),
    "make_atypon_browser_profile": (".profile", "make_atypon_browser_profile"),
    "validate_browser_profile_catalog_sync": (
        ".profile",
        "validate_browser_profile_catalog_sync",
    ),
    "HtmlExtractionFailure": (
        "paper_fetch.extraction.html.signals",
        "HtmlExtractionFailure",
    ),
    "_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS": (
        ".fetchers",
        "_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS",
    ),
    "_MemoizedFigurePageFetcher": (".fetchers", "_MemoizedFigurePageFetcher"),
    "_MemoizedImageDocumentFetcher": (".fetchers", "_MemoizedImageDocumentFetcher"),
    "_SharedBrowserFileDocumentFetcher": (
        ".fetchers",
        "_SharedBrowserFileDocumentFetcher",
    ),
    "_SharedBrowserImageDocumentFetcher": (
        ".fetchers",
        "_SharedBrowserImageDocumentFetcher",
    ),
    "_ThreadLocalSharedBrowserFileDocumentFetcher": (
        ".fetchers",
        "_ThreadLocalSharedBrowserFileDocumentFetcher",
    ),
    "_ThreadLocalSharedBrowserImageDocumentFetcher": (
        ".fetchers",
        "_ThreadLocalSharedBrowserImageDocumentFetcher",
    ),
    "_assets_matching_download_failures": (
        ".assets",
        "_assets_matching_download_failures",
    ),
    "_browser_workflow_html_payload": (
        ".html_extraction",
        "_browser_workflow_html_payload",
    ),
    "_browser_workflow_image_download_candidates": (
        ".assets",
        "_browser_workflow_image_download_candidates",
    ),
    "_build_shared_browser_file_fetcher": (
        ".fetchers",
        "_build_shared_browser_file_fetcher",
    ),
    "_build_shared_browser_image_fetcher": (
        ".fetchers",
        "_build_shared_browser_image_fetcher",
    ),
    "_cached_browser_workflow_assets": (".assets", "_cached_browser_workflow_assets"),
    "_cached_browser_workflow_markdown": (
        ".html_extraction",
        "_cached_browser_workflow_markdown",
    ),
    "_choose_browser_seed_url": (".fetchers", "_choose_browser_seed_url"),
    "_compact_failure_diagnostic": (".fetchers", "_compact_failure_diagnostic"),
    "_fetch_browser_html_payload": (".bootstrap", "_fetch_browser_html_payload"),
    "_fetch_browser_html_payload_with_fast_path": (
        ".bootstrap",
        "_fetch_browser_html_payload_with_fast_path",
    ),
    "_merge_download_attempt_results": (".assets", "_merge_download_attempt_results"),
    "_normalized_response_headers": (".fetchers", "_normalized_response_headers"),
    "bootstrap_browser_workflow": (".bootstrap", "bootstrap_browser_workflow"),
    "browser_workflow_article_from_payload": (
        ".article",
        "browser_workflow_article_from_payload",
    ),
    "build_browser_workflow_html_candidates": (
        ".shared",
        "build_browser_workflow_html_candidates",
    ),
    "build_browser_workflow_pdf_candidates": (
        ".shared",
        "build_browser_workflow_pdf_candidates",
    ),
    "download_assets": ("paper_fetch.extraction.html.assets", "download_assets"),
    "download_browser_backed_related_assets": (
        ".asset_download",
        "download_browser_backed_related_assets",
    ),
    "ensure_runtime_ready": (
        "paper_fetch.providers.browser_runtime",
        "ensure_runtime_ready",
    ),
    "extract_pdf_url_from_crossref": (".shared", "extract_pdf_url_from_crossref"),
    "extract_atypon_browser_workflow_markdown": (
        ".html_extraction",
        "extract_atypon_browser_workflow_markdown",
    ),
    "fetch_html_with_browser": (
        "paper_fetch.providers.browser_runtime",
        "fetch_html_with_browser",
    ),
    "fetch_image_document_with_browser": (
        ".fetchers",
        "fetch_image_document_with_browser",
    ),
    "fetch_pdf_with_browser": (
        "paper_fetch.providers._pdf_fallback",
        "fetch_pdf_with_playwright",
    ),
    "fetch_seeded_browser_pdf_payload": (
        ".pdf_fallback",
        "fetch_seeded_browser_pdf_payload",
    ),
    "load_runtime_config": (
        "paper_fetch.providers.browser_runtime",
        "load_runtime_config",
    ),
    "merge_browser_context_seeds": (
        "paper_fetch.providers.browser_runtime",
        "merge_browser_context_seeds",
    ),
    "merge_provider_owned_authors": (".article", "merge_provider_owned_authors"),
    "probe_runtime_status": (
        "paper_fetch.providers.browser_runtime",
        "probe_runtime_status",
    ),
    "rewrite_inline_figure_links": (".html_extraction", "rewrite_inline_figure_links"),
    "warm_browser_context": (
        "paper_fetch.providers.browser_runtime",
        "warm_browser_context",
    ),
}

__all__ = [*_EXPORTS, "time"]


def __getattr__(name: str) -> Any:
    if name == "time":
        return time
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted([*globals(), *__all__])
