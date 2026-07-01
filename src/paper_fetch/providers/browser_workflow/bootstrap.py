"""HTML bootstrap orchestration for provider browser workflows."""

from __future__ import annotations

import logging
import urllib.parse
from typing import TYPE_CHECKING

from ...extraction.html._runtime import decode_html
from ...extraction.html.signals import HtmlExtractionFailure, summarize_html
from ...http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, RequestFailure
from ...http.headers import header_value
from ...metadata.types import ProviderMetadata
from ...publisher_identity import normalize_doi
from ...runtime import RuntimeContext
from ...utils import normalize_text
from . import html_extraction as _html_extraction
from .html_extraction import (
    _browser_workflow_html_payload,
)
from .shared import (
    BrowserWorkflowDeps,
    default_browser_workflow_deps,
    preferred_html_candidate_from_landing_page as _preferred_html_candidate_from_landing_page,
)
from .._pdf_candidates import extract_pdf_candidate_urls_from_html
from .._pdf_fallback import DEFAULT_BROWSER_NAVIGATION_USER_AGENT
from ..browser_runtime import BrowserFetchedHtml, BrowserRuntimeFailure
from ..base import ProviderFailure
from ...reason_codes import NOT_SUPPORTED
from .profile import BrowserWorkflowBootstrapResult

if TYPE_CHECKING:
    from .client import BrowserWorkflowClient

logger = logging.getLogger("paper_fetch.providers.browser_workflow")

DIRECT_HTTP_HTML_FETCHER_NAME = "direct_http"


def _direct_http_referer(candidate_url: str, landing_page_url: str | None) -> str:
    landing = normalize_text(landing_page_url)
    if landing:
        return landing
    parsed = urllib.parse.urlparse(candidate_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return ""


def _direct_http_browser_user_agent(client: BrowserWorkflowClient) -> str:
    return normalize_text(client.browser_user_agent) or DEFAULT_BROWSER_NAVIGATION_USER_AGENT


def _direct_http_html_headers(
    client: BrowserWorkflowClient,
    *,
    candidate_url: str,
    landing_page_url: str | None,
) -> dict[str, str]:
    headers = {
        "User-Agent": _direct_http_browser_user_agent(client),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    referer = _direct_http_referer(candidate_url, landing_page_url)
    if referer:
        headers["Referer"] = referer
    return headers


def _direct_http_response_is_html(response: dict[str, object]) -> bool:
    content_type = header_value(response.get("headers"), "content-type").lower()
    body = response.get("body")
    if not isinstance(body, (bytes, bytearray)) or not body:
        return False
    if "html" in content_type:
        return True
    head = bytes(body[:256]).lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def _fetch_direct_http_html_preflight(
    client: BrowserWorkflowClient,
    html_candidates: list[str],
    *,
    landing_page_url: str | None,
) -> BrowserFetchedHtml:
    transport = getattr(client, "transport", None)
    if transport is None:
        raise HtmlExtractionFailure(
            "direct_http_unavailable",
            "Direct HTTP HTML preflight requires a transport.",
        )

    last_reason = "no_html_candidates"
    for candidate_url in html_candidates:
        candidate = normalize_text(candidate_url)
        if not candidate:
            continue
        headers = _direct_http_html_headers(
            client,
            candidate_url=candidate,
            landing_page_url=landing_page_url,
        )
        try:
            response = transport.request(
                "GET",
                candidate,
                headers=headers,
                timeout=DEFAULT_FULLTEXT_TIMEOUT_SECONDS,
                retry_on_transient=True,
                retry_on_rate_limit=True,
            )
        except RequestFailure as exc:
            last_reason = f"status_{exc.status_code}" if exc.status_code else exc.__class__.__name__
            continue
        except Exception as exc:
            last_reason = normalize_text(str(exc)) or exc.__class__.__name__
            continue

        status = response.get("status_code")
        if isinstance(status, int) and status >= 400:
            last_reason = f"status_{status}"
            continue
        if not _direct_http_response_is_html(response):
            content_type = header_value(response.get("headers"), "content-type")
            last_reason = f"non_html_response:{content_type or 'unknown'}"
            continue

        content_type = header_value(response.get("headers"), "content-type")
        body = response.get("body")
        html_text = decode_html(bytes(body), content_type=content_type)
        final_url = urllib.parse.urljoin(
            candidate,
            normalize_text(str(response.get("url") or "")) or candidate,
        )
        return BrowserFetchedHtml(
            source_url=candidate,
            final_url=final_url,
            html=html_text,
            response_status=status if isinstance(status, int) else None,
            response_headers=dict(response.get("headers") or {}),
            title=None,
            summary=summarize_html(html_text),
            browser_context_seed={
                "browser_user_agent": headers["User-Agent"],
                "browser_final_url": final_url,
                "paper_fetch_html_fetcher": DIRECT_HTTP_HTML_FETCHER_NAME,
            },
        )

    raise HtmlExtractionFailure(
        "direct_http_unavailable",
        f"Direct HTTP HTML preflight did not return usable HTML ({last_reason}).",
    )


def _fetch_browser_html_payload(*args, deps: BrowserWorkflowDeps | None = None, **kwargs):
    deps = deps or default_browser_workflow_deps()
    kwargs.setdefault(
        "html_fetcher",
        deps.fetch_html_with_browser,
    )
    return _html_extraction._fetch_browser_html_payload(*args, **kwargs)


def _fetch_browser_html_payload_with_fast_path(
    *args,
    deps: BrowserWorkflowDeps | None = None,
    **kwargs,
):
    deps = deps or default_browser_workflow_deps()
    kwargs.setdefault(
        "html_fetcher",
        deps.fetch_html_with_browser,
    )
    return _html_extraction._fetch_browser_html_payload_with_fast_path(
        *args, **kwargs
    )


def bootstrap_browser_workflow(
    client: BrowserWorkflowClient,
    doi: str,
    metadata: ProviderMetadata,
    *,
    allow_runtime_failure: bool = False,
    context: RuntimeContext | None = None,
    deps: BrowserWorkflowDeps | None = None,
) -> BrowserWorkflowBootstrapResult:
    deps = deps or default_browser_workflow_deps()
    context = client._runtime_context(context)
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        raise ProviderFailure(
            NOT_SUPPORTED, f"{client.name} full-text retrieval requires a DOI."
        )

    landing_page_url = str(metadata.get("landing_page_url") or "") or None
    html_candidates = client.html_candidates(normalized_doi, metadata)
    pdf_candidates = client.pdf_candidates(normalized_doi, metadata)
    result = BrowserWorkflowBootstrapResult(
        normalized_doi=normalized_doi,
        runtime=None,
        landing_page_url=landing_page_url,
        html_candidates=html_candidates,
        pdf_candidates=pdf_candidates,
    )

    profile = client.require_profile()
    preferred_html_candidate = _preferred_html_candidate_from_landing_page(
        normalized_doi,
        landing_page_url,
        hosts=profile.hosts,
    )
    logger.debug(
        "browser_workflow_candidates provider=%s doi=%s preferred_hit=%s first_candidate=%s candidate_count=%s",
        client.name,
        normalized_doi,
        bool(
            preferred_html_candidate
            and html_candidates
            and html_candidates[0] == preferred_html_candidate
        ),
        html_candidates[0] if html_candidates else None,
        len(html_candidates),
    )

    if profile.direct_http_html_preflight:
        try:
            html_result = _fetch_direct_http_html_preflight(
                client,
                html_candidates,
                landing_page_url=landing_page_url,
            )
            result.browser_context_seed = html_result.browser_context_seed
            markdown_text, extraction = deps._cached_browser_workflow_markdown(
                client,
                html_result.html,
                html_result.final_url,
                metadata=metadata,
                context=context,
            )
            result.html_payload = _browser_workflow_html_payload(
                client,
                html_result,
                markdown_text=markdown_text,
                extraction=extraction,
                fetcher=DIRECT_HTTP_HTML_FETCHER_NAME,
                warnings=result.warnings,
            )
            return result
        except HtmlExtractionFailure as exc:
            logger.debug(
                "browser_workflow_direct_http_preflight provider=%s doi=%s action=fallback reason=%s message=%s",
                client.name,
                normalized_doi,
                exc.reason,
                exc.message,
            )
        except Exception as exc:
            logger.debug(
                "browser_workflow_direct_http_preflight provider=%s doi=%s action=fallback error=%s",
                client.name,
                normalized_doi,
                normalize_text(str(exc)) or exc.__class__.__name__,
            )

    if profile.direct_playwright_html_preflight:
        try:
            if result.runtime is None:
                result.runtime = deps.load_runtime_config(
                    client.env,
                    provider=client.name,
                    doi=normalized_doi,
                )
                deps.ensure_runtime_ready(result.runtime)
            html_result = deps.fetch_html_with_fast_browser(
                html_candidates,
                publisher=client.name,
                user_agent=client.browser_user_agent,
                context=context,
                browser_config=result.runtime,
            )
            result.browser_context_seed = html_result.browser_context_seed
            markdown_text, extraction = deps._cached_browser_workflow_markdown(
                client,
                html_result.html,
                html_result.final_url,
                metadata=metadata,
                context=context,
            )
            fetcher_attr = getattr(
                deps.fetch_html_with_fast_browser,
                "paper_fetch_html_fetcher_name",
                None,
            )
            fetcher_name = (
                normalize_text(fetcher_attr)
                if isinstance(fetcher_attr, str)
                else "cloakbrowser_fast"
            )
            result.html_payload = _browser_workflow_html_payload(
                client,
                html_result,
                markdown_text=markdown_text,
                extraction=extraction,
                fetcher=fetcher_name,
                warnings=result.warnings,
            )
            return result
        except HtmlExtractionFailure as exc:
            logger.debug(
                "browser_workflow_direct_html_preflight provider=%s doi=%s action=fallback reason=%s message=%s",
                client.name,
                normalized_doi,
                exc.reason,
                exc.message,
            )
        except Exception as exc:
            logger.debug(
                "browser_workflow_direct_html_preflight provider=%s doi=%s action=fallback error=%s",
                client.name,
                normalized_doi,
                normalize_text(str(exc)) or exc.__class__.__name__,
            )

    try:
        if result.runtime is None:
            result.runtime = deps.load_runtime_config(
                client.env,
                provider=client.name,
                doi=normalized_doi,
            )
            deps.ensure_runtime_ready(result.runtime)
    except ProviderFailure as exc:
        if not allow_runtime_failure:
            raise
        result.runtime_failure = exc
        result.html_failure_reason = exc.code
        result.html_failure_message = exc.message
        return result

    try:
        html_result, html_payload = _fetch_browser_html_payload_with_fast_path(
            client,
            html_candidates,
            runtime=result.runtime,
            metadata=metadata,
            context=context,
            warnings=result.warnings,
            deps=deps,
        )
        result.browser_context_seed = html_result.browser_context_seed
        result.html_payload = html_payload
        return result
    except BrowserRuntimeFailure as exc:
        result.browser_context_seed = (
            exc.browser_context_seed or result.browser_context_seed
        )
        result.html_failure_reason = exc.kind
        result.html_failure_message = exc.message
    except HtmlExtractionFailure as exc:
        html_result = getattr(exc, "html_result", None)
        if html_result is not None:
            result.browser_context_seed = (
                getattr(html_result, "browser_context_seed", None)
                or result.browser_context_seed
            )
            for pdf_candidate in reversed(
                extract_pdf_candidate_urls_from_html(
                    getattr(html_result, "html", "") or "",
                    getattr(html_result, "final_url", "") or "",
                )
            ):
                if pdf_candidate and pdf_candidate not in result.pdf_candidates:
                    result.pdf_candidates.insert(0, pdf_candidate)
        result.html_failure_reason = exc.reason
        result.html_failure_message = exc.message

    return result
