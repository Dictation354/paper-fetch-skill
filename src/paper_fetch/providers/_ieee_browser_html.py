"""IEEE clean-browser HTML fallback."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..extraction.html import decode_html
from ..http.headers import header_value
from ..quality.html_availability import (
    HtmlQualityAssessor,
    availability_failure_message,
)
from ..reason_codes import ERROR, NO_RESULT
from ..runtime import RuntimeContext
from ..runtime_browser import browser_context_options
from ..tracing import fulltext_marker
from ..utils import normalize_text
from . import _ieee_html as ieee_html
from . import _ieee_metadata as ieee_metadata
from . import _ieee_url as ieee_url
from ._payloads import (
    build_provider_payload,
    provider_failure_diagnostics as _provider_failure_diagnostics,
)
from .base import ProviderFailure, RawFulltextPayload
from .browser_workflow.shared import BROWSER_HTML_BLOCKED_RESOURCE_TYPES
import contextlib

IEEE_BROWSER_HTML_NAVIGATION_TIMEOUT_MS = 60000
IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS = 15000
IEEE_BROWSER_HTML_DOM_WAIT_TIMEOUT_MS = 5000


def _playwright_response_headers(response: Any | None) -> dict[str, str]:
    if response is None:
        return {}
    try:
        headers = response.all_headers()
    except Exception:
        headers = getattr(response, "headers", {}) or {}
    return {
        normalize_text(str(key)).lower(): str(value)
        for key, value in dict(headers or {}).items()
        if normalize_text(str(key))
    }


def _playwright_response_status(response: Any | None) -> int | None:
    if response is None:
        return None
    try:
        return int(getattr(response, "status", 0) or 0) or None
    except Exception:
        return None


def fetch_ieee_browser_html_payload(
    *,
    provider_name: str,
    browser_user_agent: str | None,
    landing_attempt: ieee_metadata.IeeeLandingAttempt,
    document_url: str,
    rest_url: str,
    direct_html_failure: ProviderFailure | None,
    context: RuntimeContext,
    extraction_assets: Callable[
        [ieee_html.IeeeHtmlExtraction, ieee_metadata.IeeeLandingAttempt],
        list[dict[str, Any]],
    ],
) -> RawFulltextPayload:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except (
        Exception
    ) as exc:  # pragma: no cover - exercised by missing dependency deployments
        raise ProviderFailure(
            ERROR, "Playwright is not installed; cannot use IEEE browser HTML fallback."
        ) from exc

    article_number = landing_attempt.article_number
    browser_context = None
    page = None
    rest_responses: list[Any] = []
    navigation_response = None
    browser_final_url = document_url
    navigation_status: int | None = None
    payload_source = ""
    response_status: int | None = None
    response_headers: dict[str, str] = {}
    source_url = document_url
    html_text = ""

    try:
        context_kwargs = browser_context_options(
            user_agent=browser_user_agent,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        browser_context = context.new_playwright_context(
            headless=True,
            **context_kwargs,
        )

        def route_handler(route: Any) -> None:
            try:
                resource_type = normalize_text(
                    getattr(route.request, "resource_type", "")
                ).lower()
                if resource_type in BROWSER_HTML_BLOCKED_RESOURCE_TYPES:
                    route.abort()
                    return
                route.continue_()
            except Exception:
                with contextlib.suppress(Exception):
                    route.continue_()

        browser_context.route("**/*", route_handler)
        page = browser_context.new_page()

        def remember_rest_response(response: Any) -> None:
            if ieee_url._is_ieee_rest_document_url(
                str(getattr(response, "url", "") or ""), article_number
            ):
                rest_responses.append(response)

        page.on("response", remember_rest_response)
        try:
            navigation_response = page.goto(
                document_url,
                wait_until="domcontentloaded",
                timeout=IEEE_BROWSER_HTML_NAVIGATION_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            navigation_response = None
        browser_final_url = (
            normalize_text(str(getattr(page, "url", "") or "")) or document_url
        )
        navigation_status = _playwright_response_status(navigation_response)

        if not rest_responses:
            with contextlib.suppress(Exception):
                page.wait_for_timeout(IEEE_BROWSER_HTML_REST_WAIT_TIMEOUT_MS)

        for response in reversed(rest_responses):
            try:
                body = response.body()
            except Exception:
                continue
            if not isinstance(body, (bytes, bytearray)) or not body:
                continue
            source_url = ieee_url._absolute_ieee_url(
                str(getattr(response, "url", "") or rest_url), rest_url
            )
            response_headers = _playwright_response_headers(response)
            html_text = decode_html(
                bytes(body),
                content_type=header_value(response_headers, "content-type"),
            )
            response_status = _playwright_response_status(response)
            payload_source = "rest_response"
            break

        if not html_text:
            with contextlib.suppress(PlaywrightTimeoutError):
                page.wait_for_selector(
                    "#article", timeout=IEEE_BROWSER_HTML_DOM_WAIT_TIMEOUT_MS
                )
            try:
                has_article = page.locator("#article").count() > 0
            except Exception:
                has_article = False
            if not has_article:
                raise ProviderFailure(
                    NO_RESULT,
                    "IEEE browser HTML fallback did not capture REST full-text HTML or #article DOM.",
                )
            html_text = str(page.content() or "")
            browser_final_url = (
                normalize_text(str(getattr(page, "url", "") or "")) or browser_final_url
            )
            source_url = browser_final_url
            response_headers = {"content-type": "text/html"}
            response_status = navigation_status
            payload_source = "dom_article"
    except ProviderFailure:
        raise
    except Exception as exc:
        message = normalize_text(str(exc)) or exc.__class__.__name__
        raise ProviderFailure(
            ERROR, f"IEEE browser HTML fallback failed ({message})."
        ) from exc
    finally:
        if page is not None:
            with contextlib.suppress(Exception):
                page.close()
        if browser_context is not None:
            with contextlib.suppress(Exception):
                browser_context.close()

    extraction = ieee_html._extract_ieee_html(
        html_text,
        source_url,
        metadata=landing_attempt.merged_metadata,
        context=context,
    )
    diagnostics = HtmlQualityAssessor("ieee").assess(
        extraction.markdown_text,
        landing_attempt.merged_metadata,
        html_text=extraction.html_text,
        title=str(landing_attempt.merged_metadata.get("title") or ""),
        requested_url=rest_url if payload_source == "rest_response" else document_url,
        final_url=source_url,
        response_status=response_status,
        section_hints=extraction.section_hints,
    )
    if not diagnostics.accepted:
        raise ProviderFailure(NO_RESULT, availability_failure_message(diagnostics))
    content_type = header_value(response_headers, "content-type", "text/html")
    extracted_assets = extraction_assets(extraction, landing_attempt)
    return build_provider_payload(
        provider=provider_name,
        route_kind="html",
        source_url=source_url,
        content_type=content_type,
        body=extraction.html_text.encode("utf-8"),
        markdown_text=extraction.markdown_text,
        merged_metadata=landing_attempt.merged_metadata,
        diagnostics={
            "availability_diagnostics": diagnostics.to_dict(),
            "browser_html": {
                "fetcher": "playwright_html",
                "payload_source": payload_source,
                "document_url": document_url,
                "rest_url": rest_url,
                "final_url": browser_final_url,
                "navigation_status": navigation_status,
                "response_status": response_status,
                "direct_html_failure": _provider_failure_diagnostics(
                    direct_html_failure
                ),
            },
            "extraction": {
                "abstract_sections": extraction.abstract_sections,
                "section_hints": extraction.section_hints,
                "marker_counts": extraction.marker_counts,
            },
        },
        reason="Downloaded full text from the IEEE Xplore clean-browser HTML fallback route.",
        fetcher="playwright_html",
        extracted_assets=extracted_assets,
        trace_markers=[
            fulltext_marker("ieee", "fail", route="html"),
            fulltext_marker("ieee", "ok", route="browser_html"),
            fulltext_marker("ieee", "ok", route="html"),
        ],
    )
