"""Shared browser-workflow runtime helpers for Wiley/Science/PNAS."""

from __future__ import annotations

import time as time

from ...extraction.html.assets import (
    download_figure_assets_with_image_document_fetcher,
    download_supplementary_assets,
)
from ...extraction.html.signals import SciencePnasHtmlFailure
from .._browser_workflow_html_extraction import (
    _browser_workflow_html_payload,
    _cached_browser_workflow_markdown,
    extract_science_pnas_markdown,
    fetch_html_with_direct_playwright,
    rewrite_inline_figure_links,
)
from .._browser_workflow_shared import (
    build_browser_workflow_html_candidates,
    build_browser_workflow_pdf_candidates,
    extract_pdf_url_from_crossref,
)
from .._flaresolverr import (
    FlareSolverrFailure,
    ensure_runtime_ready,
    fetch_html_with_flaresolverr,
    load_runtime_config,
    merge_browser_context_seeds,
    probe_runtime_status,
    warm_browser_context_with_flaresolverr,
)
from .._pdf_fallback import PdfFallbackFailure, fetch_pdf_with_playwright
from ..browser_workflow_fetchers import (
    _IMAGE_DOCUMENT_FETCH_TIMEOUT_MS,
    _BasePlaywrightDocumentFetcher,
    _MemoizedFigurePageFetcher,
    _MemoizedImageDocumentFetcher,
    _SharedPlaywrightFileDocumentFetcher,
    _SharedPlaywrightImageDocumentFetcher,
    _ThreadLocalSharedPlaywrightFileDocumentFetcher,
    _ThreadLocalSharedPlaywrightImageDocumentFetcher,
    _build_shared_playwright_file_fetcher,
    _build_shared_playwright_image_fetcher,
    _choose_playwright_seed_url,
    _compact_failure_diagnostic,
    _flaresolverr_image_document_payload,
    _flaresolverr_image_payload_failure_reason,
    _normalized_response_headers,
    fetch_image_document_with_playwright,
)
from .article import browser_workflow_article_from_payload, merge_provider_owned_authors
from .assets import (
    _assets_matching_download_failures,
    _browser_workflow_image_download_candidates,
    _cached_browser_workflow_assets,
    _merge_download_attempt_results,
)
from .bootstrap import (
    _fetch_flaresolverr_html_payload,
    _fetch_flaresolverr_html_payload_with_fast_path,
    bootstrap_browser_workflow,
)
from .client import BrowserWorkflowClient
from .pdf_fallback import fetch_seeded_browser_pdf_payload
from .profile import BrowserWorkflowBootstrapResult, ProviderBrowserProfile

__all__ = [
    "BrowserWorkflowBootstrapResult",
    "BrowserWorkflowClient",
    "FlareSolverrFailure",
    "_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS",
    "_BasePlaywrightDocumentFetcher",
    "_MemoizedFigurePageFetcher",
    "_MemoizedImageDocumentFetcher",
    "_SharedPlaywrightFileDocumentFetcher",
    "_SharedPlaywrightImageDocumentFetcher",
    "_ThreadLocalSharedPlaywrightFileDocumentFetcher",
    "_ThreadLocalSharedPlaywrightImageDocumentFetcher",
    "_assets_matching_download_failures",
    "_browser_workflow_html_payload",
    "_browser_workflow_image_download_candidates",
    "_build_shared_playwright_file_fetcher",
    "_build_shared_playwright_image_fetcher",
    "_cached_browser_workflow_assets",
    "_cached_browser_workflow_markdown",
    "_choose_playwright_seed_url",
    "_compact_failure_diagnostic",
    "_fetch_flaresolverr_html_payload",
    "_fetch_flaresolverr_html_payload_with_fast_path",
    "_flaresolverr_image_document_payload",
    "_flaresolverr_image_payload_failure_reason",
    "_merge_download_attempt_results",
    "_normalized_response_headers",
    "PdfFallbackFailure",
    "ProviderBrowserProfile",
    "SciencePnasHtmlFailure",
    "bootstrap_browser_workflow",
    "browser_workflow_article_from_payload",
    "build_browser_workflow_html_candidates",
    "build_browser_workflow_pdf_candidates",
    "ensure_runtime_ready",
    "extract_pdf_url_from_crossref",
    "extract_science_pnas_markdown",
    "fetch_html_with_direct_playwright",
    "fetch_html_with_flaresolverr",
    "fetch_image_document_with_playwright",
    "fetch_pdf_with_playwright",
    "fetch_seeded_browser_pdf_payload",
    "load_runtime_config",
    "merge_browser_context_seeds",
    "merge_provider_owned_authors",
    "probe_runtime_status",
    "rewrite_inline_figure_links",
    "time",
    "warm_browser_context_with_flaresolverr",
    "download_figure_assets_with_image_document_fetcher",
    "download_supplementary_assets",
]
