"""Direct-HTTP HTML fetch helpers for browser-workflow-compatible providers."""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING
from collections.abc import Mapping

from ...extraction.html._runtime import decode_html
from ...extraction.html.signals import (
    HtmlExtractionFailure,
    detect_html_block,
    summarize_html,
)
from ...http import DEFAULT_FULLTEXT_TIMEOUT_SECONDS, RequestFailure
from ...http.headers import header_value
from ...utils import normalize_text
from .._pdf_fallback import DEFAULT_BROWSER_NAVIGATION_USER_AGENT
from ..browser_runtime.types import BrowserFetchedHtml

if TYPE_CHECKING:
    from .client import BrowserWorkflowClient

DIRECT_HTTP_HTML_FETCHER_NAME = "direct_http"
DIRECT_HTTP_HTML_MAX_REDIRECTS = 5
DIRECT_HTTP_REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


def _direct_http_referer(candidate_url: str, landing_page_url: str | None) -> str:
    landing = normalize_text(landing_page_url)
    if landing:
        return landing
    parsed = urllib.parse.urlparse(candidate_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}/"
    return ""


def _direct_http_browser_user_agent(client: BrowserWorkflowClient) -> str:
    return (
        normalize_text(client.browser_user_agent)
        or DEFAULT_BROWSER_NAVIGATION_USER_AGENT
    )


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
    headers = response.get("headers")
    content_type = header_value(
        headers if isinstance(headers, Mapping) else None, "content-type"
    ).lower()
    body = response.get("body")
    if not isinstance(body, (bytes, bytearray)) or not body:
        return False
    if "html" in content_type:
        return True
    head = bytes(body[:256]).lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def _direct_http_redirect_target(
    candidate_url: str, response: dict[str, object]
) -> str | None:
    status = response.get("status_code")
    if not isinstance(status, int) or status not in DIRECT_HTTP_REDIRECT_STATUS_CODES:
        return None
    headers = response.get("headers")
    location = header_value(
        headers if isinstance(headers, Mapping) else None, "location"
    )
    target = urllib.parse.urljoin(candidate_url, normalize_text(location))
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return target


def fetch_direct_http_html(
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
        redirects_followed = 0
        seen_urls = {candidate}
        while True:
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
                last_reason = (
                    f"status_{exc.status_code}"
                    if exc.status_code
                    else exc.__class__.__name__
                )
                break
            except Exception as exc:
                last_reason = normalize_text(str(exc)) or exc.__class__.__name__
                break

            status = response.get("status_code")
            if isinstance(status, int) and status in DIRECT_HTTP_REDIRECT_STATUS_CODES:
                target = _direct_http_redirect_target(candidate, response)
                if not target:
                    last_reason = f"redirect_without_location:{status}"
                    break
                if redirects_followed >= DIRECT_HTTP_HTML_MAX_REDIRECTS:
                    last_reason = f"redirect_limit:{status}"
                    break
                if target in seen_urls:
                    last_reason = f"redirect_loop:{status}"
                    break
                seen_urls.add(target)
                candidate = target
                redirects_followed += 1
                continue
            if isinstance(status, int) and status >= 400:
                last_reason = f"status_{status}"
                break
            if not _direct_http_response_is_html(response):
                content_type = header_value(response.get("headers"), "content-type")
                last_reason = f"non_html_response:{content_type or 'unknown'}"
                break

            content_type = header_value(response.get("headers"), "content-type")
            body = response.get("body")
            html_text = decode_html(bytes(body), content_type=content_type)
            summary = summarize_html(html_text)
            detected = detect_html_block(
                "", summary, status if isinstance(status, int) else None
            )
            if detected is not None:
                last_reason = detected.reason
                break
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
                summary=summary,
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
