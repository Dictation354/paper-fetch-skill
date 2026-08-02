"""IEEE landing-page acquisition with selected-browser recovery."""

from __future__ import annotations

import urllib.parse
from typing import Any
from collections.abc import Mapping

from ..extraction.html.landing import LandingRedirectLimitExceeded, fetch_landing_html
from ..extraction.html.assets import browser_asset_recovery_allowed
from ..extraction.html.signals import detect_html_block, summarize_html
from ..failure import FailureDiagnostics
from ..http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, RequestFailure
from ..http.headers import header_value
from ..publisher_identity import normalize_doi
from ..reason_codes import ERROR, NO_RESULT, NOT_SUPPORTED
from ..runtime import RuntimeContext
from ..utils import choose_public_landing_page_url, normalize_text
from . import _ieee_metadata as ieee_metadata
from . import _ieee_url as ieee_url
from . import browser_runtime
from .base import ProviderFailure, map_request_failure

MAX_IEEE_LANDING_REDIRECTS = 8
IEEE_LANDING_BROWSER_READINESS_WAIT_SECONDS = 15


def resolve_ieee_landing_url(
    client: Any,
    doi: str,
    metadata: Mapping[str, Any],
) -> str:
    article_number = ieee_url._article_number_from_metadata(metadata)
    document_url = client._document_url(article_number) if article_number else None
    return (
        choose_public_landing_page_url(
            metadata.get("landing_page_url"),
            document_url,
            f"https://doi.org/{urllib.parse.quote(doi, safe='')}",
        )
        or f"https://doi.org/{urllib.parse.quote(doi, safe='')}"
    )


def fetch_ieee_landing_attempt(
    client: Any,
    doi: str,
    metadata: Mapping[str, Any],
    *,
    context: RuntimeContext | None = None,
) -> ieee_metadata.IeeeLandingAttempt:
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        raise ProviderFailure(NOT_SUPPORTED, "IEEE full-text retrieval requires a DOI.")
    landing_url = resolve_ieee_landing_url(client, normalized_doi, metadata)
    direct_failure: ProviderFailure | None = None
    direct_diagnostics: dict[str, Any] = {}
    landing_fetch = None
    try:
        landing_fetch = fetch_landing_html(
            landing_url,
            transport=client.transport,
            headers=client._landing_headers(),
            timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
            max_redirects=MAX_IEEE_LANDING_REDIRECTS,
            raise_on_redirect_limit=True,
            retry_on_transient=True,
        )
        detected = detect_html_block(
            "",
            summarize_html(landing_fetch.html_text),
            landing_fetch.status_code,
            html_text=landing_fetch.html_text,
            response_headers=landing_fetch.headers,
        )
        if detected is not None:
            raise ProviderFailure(detected.reason, detected.message)
    except LandingRedirectLimitExceeded:
        direct_diagnostics = {"direct_reason": "redirect_limit_exceeded"}
        direct_failure = ProviderFailure(
            ERROR,
            f"IEEE landing retrieval exceeded {MAX_IEEE_LANDING_REDIRECTS} redirects.",
        )
    except RequestFailure as exc:
        direct_diagnostics = {
            "direct_status": exc.status_code,
            "direct_content_type": header_value(exc.headers, "content-type"),
            "direct_reason": str(exc),
            "direct_error_category": str(exc.error_category or ""),
        }
        if not browser_asset_recovery_allowed(
            status=exc.status_code,
            content_type=header_value(exc.headers, "content-type"),
            reason=str(exc),
            error_category=str(exc.error_category or ""),
        ):
            raise map_request_failure(exc) from exc
        direct_failure = map_request_failure(exc)
    except ProviderFailure as exc:
        direct_diagnostics = {
            "direct_status": (
                landing_fetch.status_code if landing_fetch is not None else None
            ),
            "direct_content_type": (
                header_value(landing_fetch.headers, "content-type")
                if landing_fetch is not None
                else ""
            ),
            "direct_reason": exc.message,
        }
        direct_failure = exc

    if landing_fetch is not None and direct_failure is None:
        try:
            return build_ieee_landing_attempt(
                client,
                normalized_doi,
                metadata,
                landing_url=landing_url,
                response_url=landing_fetch.final_url,
                html_text=landing_fetch.html_text,
                acquisition_source="direct_http",
                diagnostics={
                    "stage": "landing",
                    "direct_status": landing_fetch.status_code,
                    "direct_content_type": header_value(
                        landing_fetch.headers, "content-type"
                    ),
                    "browser_attempted": False,
                    "seed_source": "none",
                    "final_fetcher": "direct_http",
                },
            )
        except ProviderFailure as exc:
            direct_diagnostics = {
                "direct_status": landing_fetch.status_code,
                "direct_content_type": header_value(
                    landing_fetch.headers, "content-type"
                ),
                "direct_reason": exc.message,
            }
            direct_failure = exc

    runtime_context = client._runtime_context(context)
    runtime_config = browser_runtime.load_runtime_config(
        runtime_context.env or client.env,
        provider=client.name,
        doi=normalized_doi,
    )
    try:
        expected_article_number = (
            ieee_url._article_number_from_metadata(metadata)
            or ieee_url._article_number_from_url(landing_url)
            or ""
        )
        browser_result = browser_runtime.fetch_html_with_browser(
            [landing_url],
            publisher=client.name,
            config=runtime_config,
            runtime_context=runtime_context,
            readiness=browser_runtime.BrowserHtmlReadiness(
                wait_for_article_body=False,
                selector="#article",
                selector_text=expected_article_number or None,
                require_selector=True,
            ),
            wait_seconds=IEEE_LANDING_BROWSER_READINESS_WAIT_SECONDS,
            disable_media=True,
        )
    except browser_runtime.BrowserRuntimeFailure as exc:
        raise ProviderFailure(
            exc.kind,
            (
                "IEEE landing retrieval failed through direct HTTP and the selected "
                f"{runtime_config.backend} browser ({exc.message})."
            ),
            diagnostics=FailureDiagnostics(
                provider=client.name,
                route="landing_browser",
                stage=normalize_text(str(exc.details.get("stage") or "")) or None,
                error_category=exc.kind,
                retryable=False,
                details=dict(exc.details),
            ),
        ) from exc
    return build_ieee_landing_attempt(
        client,
        normalized_doi,
        metadata,
        landing_url=landing_url,
        response_url=browser_result.final_url,
        html_text=browser_result.html,
        acquisition_source=f"{runtime_config.backend}_browser",
        browser_context_seed=browser_result.browser_context_seed,
        diagnostics={
            "stage": "landing",
            **direct_diagnostics,
            "browser_backend": runtime_config.backend,
            "browser_attempted": True,
            "browser_status": browser_result.response_status,
            "browser_content_type": header_value(
                browser_result.response_headers, "content-type"
            ),
            "seed_source": "landing_browser",
            "final_fetcher": runtime_config.backend,
        },
    )


def build_ieee_landing_attempt(
    client: Any,
    normalized_doi: str,
    metadata: Mapping[str, Any],
    *,
    landing_url: str,
    response_url: str,
    html_text: str,
    acquisition_source: str,
    browser_context_seed: Mapping[str, Any] | None = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> ieee_metadata.IeeeLandingAttempt:
    landing_metadata = ieee_metadata._parse_landing_metadata(html_text)
    article_number = (
        ieee_url._article_number_from_metadata(landing_metadata)
        or ieee_url._article_number_from_url(response_url)
        or ieee_url._article_number_from_metadata(metadata)
        or ieee_url._article_number_from_url(landing_url)
    )
    if not article_number:
        raise ProviderFailure(
            NO_RESULT, "IEEE landing page did not expose an article number."
        )
    merged_metadata = ieee_metadata._merge_ieee_metadata(
        metadata, landing_metadata, response_url
    )
    try:
        reference_count = int(landing_metadata.get("referenceCount") or 0)
    except (TypeError, ValueError):
        reference_count = 0
    if reference_count > 0:
        try:
            reference_metadata = client._fetch_reference_metadata(
                article_number,
                client._document_url(article_number),
                expected_count=reference_count,
            )
        except RequestFailure:
            reference_metadata = []
        if reference_metadata:
            merged_metadata["references"] = reference_metadata
    if not merged_metadata.get("doi"):
        merged_metadata["doi"] = normalized_doi
    merged_metadata["article_number"] = article_number
    merged_metadata["articleNumber"] = article_number
    return ieee_metadata.IeeeLandingAttempt(
        normalized_doi=normalized_doi,
        landing_url=landing_url,
        response_url=response_url,
        html_text=html_text,
        merged_metadata=merged_metadata,
        article_number=article_number,
        landing_metadata=landing_metadata,
        acquisition_source=acquisition_source,
        browser_context_seed=dict(browser_context_seed or {}),
        diagnostics=dict(diagnostics or {}),
    )


__all__ = [
    "MAX_IEEE_LANDING_REDIRECTS",
    "build_ieee_landing_attempt",
    "fetch_ieee_landing_attempt",
    "resolve_ieee_landing_url",
]
