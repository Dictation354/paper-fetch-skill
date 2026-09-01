"""IEEE browser full-text readiness and failure diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from ..extraction.html.signals import detect_html_block, summarize_visible_html
from ..http import redact_url_for_diagnostics
from ..http.headers import header_value
from ..page_diagnostics import PageDiagnosticRequest, capture_page_diagnostic
from ..runtime import RuntimeContext
from ..reason_codes import ERROR
from ..utils import normalize_text
from . import _ieee_html as ieee_html
from . import _ieee_metadata as ieee_metadata
from . import _ieee_url as ieee_url
from .browser_runtime import BrowserRuntimeConfig, BrowserRuntimeFailure
from .base import ProviderFailure


def _playwright_timeout_error(runtime_config: BrowserRuntimeConfig) -> type[Exception]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except Exception as exc:  # pragma: no cover - missing dependency deployment
        raise ProviderFailure(
            ERROR,
            "Camoufox browser runtime requires Playwright; "
            "cannot use IEEE selected-browser HTML fallback.",
        ) from exc
    return PlaywrightTimeoutError


def _playwright_response_headers(response: Any | None) -> dict[str, str]:
    if response is None:
        return {}
    try:
        headers = response.all_headers()
    except Exception:
        headers = getattr(response, "headers", {}) or {}
    if not isinstance(headers, Mapping):
        return {}
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


@dataclass(frozen=True)
class _CapturedRestHtml:
    source_url: str
    headers: dict[str, str]
    html_text: str
    status: int | None


@dataclass(frozen=True)
class _RestHtmlSelection:
    selected: _CapturedRestHtml | None
    latest_invalid: _CapturedRestHtml | None
    response_count: int
    invalid_response_count: int


@dataclass(frozen=True)
class _BrowserFailureContext:
    runtime_context: RuntimeContext
    provider_name: str
    landing_attempt: ieee_metadata.IeeeLandingAttempt
    runtime_config: BrowserRuntimeConfig
    document_url: str
    rest_url: str
    final_url: str
    navigation_status: int | None
    navigation_headers: Mapping[str, str]


def _captured_rest_html(
    response: Any,
    rest_url: str,
) -> _CapturedRestHtml | None:
    # A Playwright Response cannot provide a bounded/streaming body read.  Keep
    # metadata for diagnostics, while article readiness comes from the loaded
    # page DOM.  The direct transport owns any future REST replay.
    headers = _playwright_response_headers(response)
    return _CapturedRestHtml(
        source_url=ieee_url._absolute_ieee_url(
            str(getattr(response, "url", "") or rest_url),
            rest_url,
        ),
        headers=headers,
        html_text="",
        status=_playwright_response_status(response),
    )


def _rest_html_candidate_is_valid(
    candidate: _CapturedRestHtml,
    article_number: str = "",
) -> bool:
    if candidate.status is not None and not 200 <= candidate.status < 300:
        return False
    content_type = normalize_text(
        header_value(candidate.headers, "content-type")
    ).lower()
    if content_type and "html" not in content_type and "xml" not in content_type:
        return False
    article = ieee_html._find_ieee_article(candidate.html_text)
    if article is None:
        return False
    normalized_article_number = normalize_text(article_number)
    return not normalized_article_number or normalized_article_number in str(article)


def _capture_rest_html(
    rest_responses: list[Any],
    rest_url: str,
    article_number: str = "",
) -> _RestHtmlSelection:
    selected: _CapturedRestHtml | None = None
    latest_invalid: _CapturedRestHtml | None = None
    invalid_response_count = 0
    for response in reversed(rest_responses):
        candidate = _captured_rest_html(response, rest_url)
        if candidate is None:
            invalid_response_count += 1
            continue
        if _rest_html_candidate_is_valid(candidate, article_number):
            if selected is None:
                selected = candidate
            continue
        invalid_response_count += 1
        if latest_invalid is None:
            latest_invalid = candidate
    return _RestHtmlSelection(
        selected=selected,
        latest_invalid=latest_invalid,
        response_count=len(rest_responses),
        invalid_response_count=invalid_response_count,
    )


def _page_has_article(page: Any, article_number: str = "") -> bool:
    try:
        if page.locator("#article").count() <= 0:
            return False
    except Exception:
        return False
    normalized_article_number = normalize_text(article_number)
    return not normalized_article_number or normalized_article_number in _page_content(
        page
    )


def _page_content(page: Any) -> str:
    try:
        return str(page.content() or "")
    except Exception:
        return ""


def _page_title(page: Any) -> str:
    try:
        return normalize_text(str(page.title() or ""))
    except Exception:
        return ""


def _capture_failure_page_diagnostics(
    failure_context: _BrowserFailureContext,
    *,
    failure_kind: str,
    stage: str,
    rest_selection: _RestHtmlSelection,
    page_html: str,
    page_title: str,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "stage": stage,
        "document_url": redact_url_for_diagnostics(failure_context.document_url),
        "rest_response_count": rest_selection.response_count,
        "invalid_rest_response_count": rest_selection.invalid_response_count,
    }
    diagnostic_paths: list[str] = []
    invalid_rest = rest_selection.latest_invalid
    if invalid_rest is not None:
        rest_diagnostic = capture_page_diagnostic(
            failure_context.runtime_context,
            PageDiagnosticRequest(
                provider=failure_context.provider_name,
                route="browser_html_rest",
                attempt=1,
                failure_code=failure_kind,
                stage=stage,
                html_text=invalid_rest.html_text,
                doi=failure_context.landing_attempt.normalized_doi,
                target_url=failure_context.rest_url,
                final_url=invalid_rest.source_url,
                backend="camoufox",
                response_status=invalid_rest.status,
                summary=summarize_visible_html(invalid_rest.html_text),
                details={"selectors": {"article": False}},
            ),
        )
        details["rest_response_diagnostic"] = rest_diagnostic
        if diagnostic_path := normalize_text(
            str(rest_diagnostic.get("diagnostic_path") or "")
        ):
            diagnostic_paths.append(diagnostic_path)
    if page_html:
        page_diagnostic = capture_page_diagnostic(
            failure_context.runtime_context,
            PageDiagnosticRequest(
                provider=failure_context.provider_name,
                route="browser_html_dom",
                attempt=1,
                failure_code=failure_kind,
                stage=stage,
                html_text=page_html,
                doi=failure_context.landing_attempt.normalized_doi,
                target_url=failure_context.document_url,
                final_url=failure_context.final_url,
                backend="camoufox",
                response_status=failure_context.navigation_status,
                title=page_title,
                summary=summarize_visible_html(page_html),
                details={"selectors": {"article": False}},
            ),
        )
        details["page_diagnostic"] = page_diagnostic
        if diagnostic_path := normalize_text(
            str(page_diagnostic.get("diagnostic_path") or "")
        ):
            diagnostic_paths.append(diagnostic_path)
    if diagnostic_paths:
        details["diagnostic_path"] = diagnostic_paths[-1]
        details["diagnostic_paths"] = diagnostic_paths
    return details


def _unready_browser_failure(
    failure_context: _BrowserFailureContext,
    *,
    navigation_timed_out: bool,
    rest_selection: _RestHtmlSelection,
    page_html: str,
    page_title: str,
) -> BrowserRuntimeFailure:
    block_candidates: list[tuple[str, str, int | None]] = []
    if rest_selection.latest_invalid is not None:
        block_candidates.append(
            (
                "rest_response",
                rest_selection.latest_invalid.html_text,
                rest_selection.latest_invalid.status,
            )
        )
    block_candidates.append(
        ("document_dom", page_html, failure_context.navigation_status)
    )
    for payload_source, candidate_html, status in block_candidates:
        if not candidate_html:
            continue
        detected = detect_html_block(
            page_title if payload_source == "document_dom" else "",
            summarize_visible_html(candidate_html),
            status,
            html_text=candidate_html,
            response_headers=(
                failure_context.navigation_headers
                if payload_source == "document_dom"
                else (
                    rest_selection.latest_invalid.headers
                    if rest_selection.latest_invalid is not None
                    else {}
                )
            ),
        )
        if detected is None:
            continue
        details = _capture_failure_page_diagnostics(
            failure_context,
            failure_kind=detected.reason,
            stage="block_detection",
            rest_selection=rest_selection,
            page_html=page_html,
            page_title=page_title,
        )
        details["status"] = status
        details["payload_source"] = payload_source
        if detected.reason == "aws_waf_challenge":
            details.update({"challenge_provider": "aws_waf"})
        return BrowserRuntimeFailure(
            detected.reason,
            detected.message,
            details=details,
        )

    if navigation_timed_out:
        failure_kind = "browser_navigation_timeout"
        stage = "navigation"
        message = (
            "IEEE browser navigation timed out before REST full-text HTML or "
            "#article DOM became ready."
        )
    elif rest_selection.invalid_response_count:
        failure_kind = "browser_rest_wait_timeout"
        stage = "rest_readiness"
        message = (
            "IEEE browser HTML fallback received REST responses, but none exposed "
            "a valid #article before the readiness timeout."
        )
    else:
        failure_kind = "browser_article_not_ready"
        stage = "dom_readiness"
        message = (
            "IEEE browser HTML fallback did not capture valid REST full-text HTML "
            "or #article DOM."
        )
    details = _capture_failure_page_diagnostics(
        failure_context,
        failure_kind=failure_kind,
        stage=stage,
        rest_selection=rest_selection,
        page_html=page_html,
        page_title=page_title,
    )
    return BrowserRuntimeFailure(failure_kind, message, details=details)
