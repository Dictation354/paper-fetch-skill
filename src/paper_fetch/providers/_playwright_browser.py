"""Shared Playwright helpers for browser-workflow provider access."""

from __future__ import annotations

import base64
import contextlib
import logging
import time
import urllib.parse
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from ..extraction.html.signals import (
    detect_html_block,
    summarize_html,
    summarize_visible_html,
)
from ..http import (
    BrowserNetworkGuard,
    RequestCancelledError,
    SafeRemoteUrlPolicy,
    diagnostic_url_payload,
    hosts_from_urls,
    provider_allowed_hosts,
)
from ..page_diagnostics import PageDiagnosticRequest, capture_page_diagnostic
from ..provider_catalog import compile_route_execution_policy_for_kind
from ..quality.html_availability import choose_parser, extract_page_title
from ..quality.html_signals import looks_like_abstract_redirect
from ..quality.reason_codes import (
    ABSTRACT_ONLY,
    AWS_WAF_CHALLENGE,
    CLOUDFLARE_CHALLENGE,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
)
from ..reason_codes import (
    BROWSER_CONTEXT_CREATE_FAILED,
    BROWSER_PAGE_CREATE_FAILED,
)
from ..runtime_browser import (
    ManagedBrowserError,
    browser_page_user_agent,
)
from ..utils import normalize_text
from ._atypon_browser_workflow_profiles import publisher_profile
from .browser_runtime.context import open_browser_context
from .browser_runtime.seed import (
    browser_context_seed_from_mapping,
    filter_browser_cookies_for_url,
    merge_browser_context_seeds,
)
from .browser_runtime.types import (
    BrowserFetchedHtml,
    BrowserHtmlFetchOptions,
    BrowserHtmlReadiness,
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
    BrowserStagedStorageState,
    BrowserWarmResult,
)
from .browser_workflow.fetchers.context import (
    _browser_response_headers,
    _browser_response_status,
    _runtime_figure_page_session,
)
from .browser_workflow.fetchers.readiness import (
    BodyDomReadinessResult,
    wait_for_atypon_body_dom_ready,
)
from .browser_workflow.shared import BROWSER_HTML_BLOCKED_RESOURCE_TYPES

if TYPE_CHECKING:
    from ..runtime import RuntimeContext
    from .browser_runtime import BrowserImagePayload


def _runtime_paths():
    from .browser_runtime import paths as runtime_paths

    return runtime_paths


logger = logging.getLogger("paper_fetch.providers.playwright")

DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS = 120000
DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS = 8
DEFAULT_BROWSER_RUNTIME_WARM_WAIT_SECONDS = 1
MAX_BROWSER_SCREENSHOT_BYTES = 16 * 1024 * 1024
DEFAULT_BROWSER_HTML_READINESS = BrowserHtmlReadiness()
DEFAULT_BROWSER_HTML_FETCH_OPTIONS = BrowserHtmlFetchOptions()
_IMAGE_RESPONSE_BLOCKED_BY_HTML_WRAPPER = "image_response_blocked_by_html_wrapper"
_IMAGE_PAYLOAD_RESPONSE_ATTR = "_paper_fetch_top_level_response"
_IMAGE_PAYLOAD_TIMEOUT_ATTR = "_paper_fetch_image_payload_timeout_ms"
_IMAGE_PAYLOAD_FAILURE_ATTR = "_paper_fetch_image_payload_failure"
_STABLE_BROWSER_ACCESS_FAILURE_KINDS = frozenset(
    {
        ABSTRACT_ONLY,
        AWS_WAF_CHALLENGE,
        CLOUDFLARE_CHALLENGE,
        PUBLISHER_ACCESS_DENIED,
        PUBLISHER_PAYWALL,
        REDIRECTED_TO_ABSTRACT,
        "iop_captcha_challenge",
        "iop_radware_challenge",
    }
)
_SELECTOR_TEXT_READINESS_SCRIPT = """
({ selector, expectedText }) => {
  let node = null;
  try {
    node = document.querySelector(selector);
  } catch (error) {
    return false;
  }
  if (!node) {
    return false;
  }
  if (!expectedText) {
    return true;
  }
  const markup = node.outerHTML || node.textContent || '';
  return markup.includes(expectedText);
}
"""

PlaywrightRuntimeConfig = BrowserRuntimeConfig
PlaywrightBrowserFailure = BrowserRuntimeFailure


def _same_site_navigation(candidate_url: str, final_url: str) -> bool:
    candidate_host = normalize_text(
        urllib.parse.urlsplit(candidate_url).hostname
    ).lower()
    final_host = normalize_text(urllib.parse.urlsplit(final_url).hostname).lower()
    if not candidate_host or not final_host:
        return False
    return bool(
        final_host == candidate_host
        or final_host.endswith(f".{candidate_host}")
        or candidate_host.endswith(f".{final_host}")
    )


def _cookie_state(seed: Mapping[str, Any] | None) -> dict[tuple[str, str, str], str]:
    state: dict[tuple[str, str, str], str] = {}
    for cookie in list((seed or {}).get("browser_cookies") or []):
        if not isinstance(cookie, Mapping):
            continue
        key = (
            normalize_text(str(cookie.get("name") or "")),
            normalize_text(str(cookie.get("domain") or "")).lower(),
            normalize_text(str(cookie.get("path") or "")) or "/",
        )
        if key[0]:
            state[key] = str(cookie.get("value") or "")
    return state


def _cookie_delta(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> dict[str, int]:
    before_state = _cookie_state(before)
    after_state = _cookie_state(after)
    return {
        "added": len(after_state.keys() - before_state.keys()),
        "updated": sum(
            1
            for key in before_state.keys() & after_state.keys()
            if before_state[key] != after_state[key]
        ),
        "removed": len(before_state.keys() - after_state.keys()),
    }


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalized_content_type(value: str | None) -> str:
    return normalize_text(str(value or "")).split(";", 1)[0].lower()


def _capture_expected_response(page: Any, request_url: str) -> Any:
    response = getattr(page, _IMAGE_PAYLOAD_RESPONSE_ATTR, None)
    if response is not None:
        return response
    timeout_ms = (
        _safe_int(getattr(page, _IMAGE_PAYLOAD_TIMEOUT_ATTR, None))
        or DEFAULT_BROWSER_RUNTIME_MAX_TIMEOUT_MS
    )
    try:
        expected_response = page.expect_response(
            lambda response: (
                normalize_text(str(getattr(response, "url", "") or "")) == request_url
            ),
            timeout=timeout_ms,
        )
    except Exception:
        return None
    if not hasattr(expected_response, "__enter__"):
        return getattr(expected_response, "value", expected_response)
    try:
        with expected_response as response_info:
            pass
        return getattr(response_info, "value", None)
    except Exception:
        return None


def _clear_image_payload_failure(page: Any) -> None:
    with contextlib.suppress(Exception):
        delattr(page, _IMAGE_PAYLOAD_FAILURE_ATTR)


def _record_image_payload_failure(page: Any, values: Mapping[str, Any]) -> None:
    with contextlib.suppress(Exception):
        setattr(page, _IMAGE_PAYLOAD_FAILURE_ATTR, dict(values))


def _capture_image_payload(
    page: Any,
    *,
    request_url: str,
    final_url: str,
) -> BrowserImagePayload | None:
    _clear_image_payload_failure(page)
    normalized_request_url = normalize_text(request_url)
    normalized_final_url = normalize_text(final_url) or normalized_request_url
    response = _capture_expected_response(page, normalized_request_url)
    status = _browser_response_status(response, zero_as_none=False) or 200
    headers = _browser_response_headers(response)
    content_type = _normalized_content_type(headers.get("content-type"))

    html = ""
    try:
        html = str(page.content() or "")
    except Exception:
        html = ""
    image_element = None
    try:
        image_element = page.query_selector("img")
    except Exception:
        image_element = None
    width = 0
    height = 0
    loaded = False
    discovered_image_url = ""
    if image_element is not None:
        try:
            image_info = image_element.evaluate(
                """
                (image) => ({
                  width: image.naturalWidth || 0,
                  height: image.naturalHeight || 0,
                  complete: !!image.complete,
                  url: image.currentSrc || image.src || '',
                })
                """
            )
        except Exception:
            image_info = None
        if isinstance(image_info, Mapping):
            width = max(0, _safe_int(image_info.get("width")))
            height = max(0, _safe_int(image_info.get("height")))
            loaded = bool(image_info.get("complete")) and width > 0 and height > 0
            discovered_url = normalize_text(str(image_info.get("url") or ""))
            if discovered_url.lower().startswith(("http://", "https://")):
                discovered_image_url = discovered_url
                normalized_final_url = discovered_url

    response_is_image = content_type.startswith("image/") and status < 400
    discovered_loaded_image = bool(discovered_image_url and loaded)
    if normalized_final_url.lower().startswith(("http://", "https://")) and (
        response_is_image or discovered_loaded_image
    ):
        return {
            "streamOnly": True,
            "contentType": content_type if response_is_image else "image/*",
            "url": normalized_final_url,
            "status": status if response_is_image else 200,
            "width": width,
            "height": height,
        }

    try:
        title = normalize_text(str(page.title() or ""))
    except Exception:
        title = ""
    if not title and html:
        try:
            title = extract_page_title(BeautifulSoup(html, choose_parser())) or ""
        except Exception:
            title = ""
    summary = summarize_visible_html(html) if normalize_text(html) else ""
    detected = detect_html_block(
        title or "",
        summary,
        status,
        html_text=html,
        response_headers=headers,
    )
    reason = (
        detected.reason
        if detected is not None
        else _IMAGE_RESPONSE_BLOCKED_BY_HTML_WRAPPER
    )
    _record_image_payload_failure(
        page,
        {
            "reason": reason,
            **diagnostic_url_payload(normalized_final_url),
            "status": status,
            "content_type": content_type,
            "title": title,
            "summary": summary,
        },
    )
    return None


def _context_seed(
    context: Any, *, final_url: str, user_agent: str | None, backend: str
) -> dict[str, Any]:
    from .browser_runtime.seed import browser_context_seed_from_session

    return browser_context_seed_from_session(
        context,
        final_url=final_url,
        user_agent=user_agent,
        backend=backend,
    )


def _safe_close(value: Any) -> None:
    if value is None:
        return
    with contextlib.suppress(Exception):
        value.close()


def _raise_if_cancelled(runtime_context: RuntimeContext | None) -> None:
    cancel_check = getattr(runtime_context, "cancel_check", None)
    if callable(cancel_check) and cancel_check() is True:
        raise RequestCancelledError("Request cancelled.")


def _storage_state_path(config: PlaywrightRuntimeConfig) -> Path | None:
    return _runtime_paths().storage_state_path(config)


def _storage_context_options(config: PlaywrightRuntimeConfig) -> dict[str, Any]:
    return _runtime_paths().storage_context_options(config)


def _storage_origin_matches_url(origin: Mapping[str, Any], url: str | None) -> bool:
    return _runtime_paths().storage_origin_matches_url(origin, url)


def _filtered_storage_state_payload(
    context: Any, *, url: str
) -> Mapping[str, Any] | None:
    return _runtime_paths().filtered_storage_state_payload(context, url=url)


def _stage_storage_state(
    context: Any,
    config: PlaywrightRuntimeConfig,
    *,
    filter_url: str | None = None,
) -> tuple[BrowserStagedStorageState | None, dict[str, Any]]:
    stage, result = _runtime_paths().stage_storage_state(
        context,
        config,
        filter_url=filter_url,
    )
    if result.get("attempted") and not result.get("staged"):
        logger.debug(
            "browser_storage_state provider=%s action=stage_failed path=%s",
            config.provider,
            result.get("path"),
        )
    return stage, result


def _navigate_browser_page(
    page: Any,
    *,
    url: str,
    timeout_ms: int,
    return_image_payload: bool,
) -> Any:
    if not return_image_payload:
        return page.goto(url, wait_until="commit", timeout=timeout_ms)

    with contextlib.suppress(Exception):
        setattr(page, _IMAGE_PAYLOAD_TIMEOUT_ATTR, timeout_ms)
    response = None
    top_level_response = None
    try:
        with page.expect_response(
            lambda candidate_response: (
                normalize_text(str(getattr(candidate_response, "url", "") or "")) == url
            ),
            timeout=timeout_ms,
        ) as response_info:
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
        try:
            top_level_response = response_info.value
        except Exception:
            top_level_response = response
    except Exception:
        if response is None:
            raise
        top_level_response = response

    with contextlib.suppress(Exception):
        setattr(
            page,
            _IMAGE_PAYLOAD_RESPONSE_ATTR,
            top_level_response if top_level_response is not None else response,
        )
    return response


def _wait_for_browser_html_readiness(
    page: Any,
    *,
    publisher: str,
    readiness: BrowserHtmlReadiness,
    wait_seconds: int,
    timeout_ms: int,
    request_started: float,
    return_image_payload: bool,
    runtime_context: RuntimeContext | None,
    candidate_trace: dict[str, Any],
    readiness_timeout_seconds: float | None = None,
) -> BodyDomReadinessResult | None:
    if return_image_payload:
        return None

    readiness_operation_started = time.monotonic()
    normalized_selector = normalize_text(readiness.selector)
    selector_text = normalize_text(readiness.selector_text)
    body_readiness = None
    selector_wait_attempted = False
    if readiness.wait_for_article_body:
        _raise_if_cancelled(runtime_context)
        remaining_timeout_seconds = max(
            0.0,
            (float(timeout_ms) / 1000.0) - (time.monotonic() - request_started),
        )
        readiness_started = time.monotonic()
        body_timeout_seconds = (
            min(readiness_timeout_seconds, remaining_timeout_seconds)
            if readiness_timeout_seconds is not None
            else min(max(float(wait_seconds), 20.0), remaining_timeout_seconds)
        )
        body_readiness = wait_for_atypon_body_dom_ready(
            page,
            publisher,
            timeout_seconds=max(0.0, body_timeout_seconds),
        )
        candidate_trace["dom_readiness_seconds"] = round(
            time.monotonic() - readiness_started, 3
        )
        candidate_trace["dom_readiness_attempted"] = body_readiness.attempted
        candidate_trace["dom_readiness_ready"] = body_readiness.ready
        candidate_trace["dom_readiness_selector"] = getattr(
            body_readiness, "selector", None
        )
        candidate_trace["dom_readiness_text_length"] = getattr(
            body_readiness, "text_length", 0
        )
        candidate_trace["dom_readiness_paragraph_count"] = getattr(
            body_readiness, "paragraph_count", 0
        )
        candidate_trace["dom_readiness_heading_count"] = getattr(
            body_readiness, "heading_count", 0
        )
        candidate_trace["dom_readiness_result"] = (
            "ready"
            if body_readiness.ready
            else ("timeout" if body_readiness.attempted else "unsupported")
        )
    elif normalized_selector and wait_seconds > 0:
        _raise_if_cancelled(runtime_context)
        selector_wait_attempted = True
        remaining_timeout_ms = max(
            1,
            int(
                ((float(timeout_ms) / 1000.0) - (time.monotonic() - request_started))
                * 1000
            ),
        )
        selector_budget_ms = (
            max(1, int(readiness_timeout_seconds * 1000))
            if readiness_timeout_seconds is not None
            else max(1, int(wait_seconds) * 1000)
        )
        selector_timeout_ms = min(
            selector_budget_ms,
            remaining_timeout_ms,
        )
        selector_started = time.monotonic()
        try:
            if selector_text:
                page.wait_for_function(
                    _SELECTOR_TEXT_READINESS_SCRIPT,
                    arg={
                        "selector": normalized_selector,
                        "expectedText": selector_text,
                    },
                    timeout=selector_timeout_ms,
                )
            else:
                page.wait_for_selector(
                    normalized_selector,
                    state="attached",
                    timeout=selector_timeout_ms,
                )
        except Exception as exc:
            candidate_trace["selector_readiness_ready"] = False
            candidate_trace["selector_readiness_error_type"] = type(exc).__name__
        else:
            candidate_trace["selector_readiness_ready"] = True
        candidate_trace["selector_readiness_attempted"] = True
        candidate_trace["selector_readiness_required"] = bool(
            readiness.require_selector
        )
        candidate_trace["selector_readiness_expected_text"] = selector_text or None
        candidate_trace["selector_readiness_seconds"] = round(
            time.monotonic() - selector_started,
            3,
        )
        candidate_trace["dom_readiness_result"] = (
            "ready" if candidate_trace.get("selector_readiness_ready") else "timeout"
        )

    if (
        (body_readiness is None or not body_readiness.attempted)
        and not selector_wait_attempted
        and wait_seconds > 0
    ):
        _raise_if_cancelled(runtime_context)
        remaining_wait_ms = max(
            0,
            int(
                ((float(timeout_ms) / 1000.0) - (time.monotonic() - request_started))
                * 1000
            ),
        )
        fixed_wait_ms = (
            min(
                remaining_wait_ms,
                max(0, int(readiness_timeout_seconds * 1000)),
            )
            if readiness_timeout_seconds is not None
            else min(max(0, int(wait_seconds)) * 1000, remaining_wait_ms)
        )
        if fixed_wait_ms > 0:
            page.wait_for_timeout(fixed_wait_ms)
        _raise_if_cancelled(runtime_context)
        candidate_trace["dom_readiness_result"] = "fixed_wait"
    if wait_seconds > 0:
        readiness_elapsed = max(
            0.0,
            time.monotonic() - readiness_operation_started,
        )
        candidate_trace["dom_readiness_seconds"] = round(
            readiness_elapsed,
            3,
        )
        if runtime_context is not None and hasattr(
            runtime_context, "accumulate_stage_timing"
        ):
            with contextlib.suppress(Exception):
                runtime_context.accumulate_stage_timing(
                    "dom_readiness_seconds",
                    elapsed=readiness_elapsed,
                )
    return body_readiness


def _prepare_provider_browser_page(
    page: Any,
    *,
    publisher: str,
    timeout_ms: int,
    candidate_trace: dict[str, Any],
) -> None:
    prepare_browser_page = publisher_profile(publisher).prepare_browser_page
    if prepare_browser_page is None:
        return
    preparation_started = time.monotonic()
    try:
        preparation = prepare_browser_page(page, timeout_ms=timeout_ms)
        if isinstance(preparation, Mapping):
            candidate_trace["provider_page_preparation"] = dict(preparation)
    except Exception as exc:
        candidate_trace["provider_page_preparation"] = {
            "attempted": True,
            "error_type": type(exc).__name__,
        }
    candidate_trace["provider_page_preparation_seconds"] = round(
        time.monotonic() - preparation_started,
        3,
    )


def _browser_html_summary(publisher: str, html_text: str) -> str:
    if normalize_text(publisher).lower() == "ieee":
        return summarize_visible_html(html_text)
    return summarize_html(html_text)


def _browser_page_failure_details(
    *,
    trace: Mapping[str, Any],
    runtime_context: RuntimeContext | None,
    request: PageDiagnosticRequest,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "trace": dict(trace),
        "stage": request.stage,
        "final_url": diagnostic_url_payload(request.final_url or ""),
        "response_status": request.response_status,
        "title_summary": (request.title or "")[:500] or None,
        "page_summary": (request.summary or "")[:1000] or None,
    }
    if request.failure_code == "aws_waf_challenge":
        details.update(
            {
                "challenge_provider": "aws_waf",
                "legacy_reason_code": "cloudflare_challenge",
            }
        )
    if runtime_context is None:
        return details
    diagnostic = capture_page_diagnostic(runtime_context, request)
    details["failure_diagnostic"] = diagnostic
    diagnostic_path = normalize_text(str(diagnostic.get("diagnostic_path") or ""))
    if diagnostic_path:
        details["diagnostic_path"] = diagnostic_path
    return details


def _lightweight_seed_rejection(
    *,
    status: int | None,
    requested_url: str,
    final_url: str,
    detected: Any | None,
) -> tuple[str, str] | None:
    if status is not None and status >= 400:
        return f"http_{status}", f"Browser warm navigation returned HTTP {status}."
    if not _same_site_navigation(requested_url, final_url):
        return (
            "warm_cross_site_redirect",
            "Browser warm navigation left the provider host.",
        )
    if looks_like_abstract_redirect(requested_url, final_url):
        return (
            REDIRECTED_TO_ABSTRACT,
            "Browser warm navigation redirected to an abstract page.",
        )
    if detected is not None:
        return detected.reason, detected.message
    return None


def _candidate_deadline_failure(
    last_failure: PlaywrightBrowserFailure | None,
    *,
    trace: Mapping[str, Any],
) -> PlaywrightBrowserFailure:
    timeout_failure = PlaywrightBrowserFailure(
        "browser_connect_timeout",
        "Browser HTML request deadline was exhausted before another candidate.",
        details={"trace": dict(trace)},
    )
    if (
        last_failure is None
        or normalize_text(last_failure.kind).lower()
        not in _STABLE_BROWSER_ACCESS_FAILURE_KINDS
    ):
        return timeout_failure

    details = dict(last_failure.details or {})
    details["trace"] = dict(trace)
    details["candidate_deadline_failure"] = {
        "failure_code": timeout_failure.kind,
        "message": timeout_failure.message,
    }
    last_failure.details = details
    return last_failure


def _candidate_failure_outcome(
    observed_failure: PlaywrightBrowserFailure | None,
    candidate_failure: PlaywrightBrowserFailure,
    *,
    trace: Mapping[str, Any],
) -> PlaywrightBrowserFailure:
    """Keep an observed access boundary ahead of later transport failures."""

    if (
        observed_failure is None
        or normalize_text(observed_failure.kind).lower()
        not in _STABLE_BROWSER_ACCESS_FAILURE_KINDS
        or normalize_text(candidate_failure.kind).lower()
        in _STABLE_BROWSER_ACCESS_FAILURE_KINDS
    ):
        return candidate_failure

    details = dict(observed_failure.details or {})
    details["trace"] = dict(trace)
    subsequent_failures = list(details.get("subsequent_candidate_failures") or [])
    subsequent_failures.append(
        {
            "failure_code": candidate_failure.kind,
            "message": candidate_failure.message,
        }
    )
    details["subsequent_candidate_failures"] = subsequent_failures
    observed_failure.details = details
    return observed_failure


def _capture_page_screenshot(
    page: Any,
    *,
    enabled: bool,
    timeout_provider: Callable[[], int],
) -> str | None:
    if not enabled:
        return None
    try:
        timeout_ms = timeout_provider()
        if timeout_ms <= 0:
            raise TimeoutError("Browser screenshot deadline exhausted.")
        payload = page.screenshot(type="png", timeout=timeout_ms)
    except Exception:
        return None
    if isinstance(payload, bytes):
        if len(payload) > MAX_BROWSER_SCREENSHOT_BYTES:
            return None
        return base64.b64encode(payload).decode("ascii")
    return payload if isinstance(payload, str) else None


def _seed_browser_html_context(
    browser_context: Any,
    *,
    browser_context_seed: Mapping[str, Any] | None,
    candidate_url: str | None,
    trace: dict[str, Any],
) -> None:
    """Apply a transient provider-scoped cookie seed before page navigation."""

    typed_seed = browser_context_seed_from_mapping(browser_context_seed)
    cookies = filter_browser_cookies_for_url(
        list(typed_seed.get("browser_cookies") or []),
        candidate_url,
    )
    seed_trace: dict[str, Any] = {
        "provided": browser_context_seed is not None,
        "cookie_count": len(cookies),
        "applied": False,
        "user_agent_reused": False,
    }
    trace["browser_context_seed"] = seed_trace
    if not cookies:
        seed_trace["reason"] = "no_compatible_cookies"
        return
    try:
        browser_context.add_cookies(cookies)
    except Exception as exc:
        seed_trace["reason"] = "cookie_injection_failed"
        seed_trace["error_type"] = type(exc).__name__
        raise PlaywrightBrowserFailure(
            "invalid_browser_context_seed",
            "Failed to apply transient browser cookies before HTML retry.",
            browser_context_seed=typed_seed,
            details={"trace": trace},
        ) from exc
    seed_trace["applied"] = True
    seed_trace["reason"] = "cookies_applied"


def _active_browser_resource_types(
    *,
    backend_name: str,
    disable_media: bool,
    options: BrowserHtmlFetchOptions,
) -> set[str]:
    if options.return_image_payload:
        return set()
    configured = {
        normalize_text(str(item)).lower()
        for item in (options.blocked_resource_types or ())
        if normalize_text(str(item))
    }
    if not disable_media:
        return configured
    if options.blocked_resource_types is None and backend_name != "camoufox":
        # Preserve the established Playwright fast-attempt policy for profiles
        # (including Science) that did not opt into provider-specific blocking.
        configured.update(BROWSER_HTML_BLOCKED_RESOURCE_TYPES)
    else:
        # Camoufox's existing default only blocks media; explicit provider
        # policies remain exact on either backend.
        configured.add("media")
    return configured


def _open_browser_html_context(
    config: PlaywrightRuntimeConfig,
    *,
    runtime_context: RuntimeContext | None,
    shared_page_session: Any | None,
    trace: dict[str, Any],
) -> tuple[Any, Any, Any | None]:
    manager = None
    browser_context = None
    page = None
    reused = False
    connect_started = time.monotonic()
    try:
        if (
            shared_page_session is not None
            and shared_page_session.context is not None
            and shared_page_session.page is not None
        ):
            reused = True
            manager = shared_page_session.manager
            browser_context = shared_page_session.context
            page = shared_page_session.page
        else:
            manager, browser_context = open_browser_context(
                config,
                runtime_context=runtime_context,
            )
        trace["runtime_page_reused"] = reused
        trace["browser_connect_seconds"] = round(time.monotonic() - connect_started, 3)
        external_diagnostics = getattr(
            browser_context, "_paper_fetch_external_cdp_diagnostics", None
        )
        if isinstance(external_diagnostics, Mapping):
            trace["external_cdp_context"] = dict(external_diagnostics)
        elif config.cdp_endpoint:
            trace["external_cdp_context"] = {
                "external_cdp": True,
                "borrowed_existing_context": None,
                "ignored_context_options": [],
                "storage_state_cookie_count": None,
            }
        return manager, browser_context, page
    except PlaywrightBrowserFailure:
        if not reused:
            _safe_close(browser_context)
            _safe_close(manager)
        raise
    except ManagedBrowserError as exc:
        trace["browser_connect_seconds"] = round(time.monotonic() - connect_started, 3)
        trace["browser_failure"] = dict(exc.details)
        if not reused:
            _safe_close(browser_context)
            _safe_close(manager)
        raise PlaywrightBrowserFailure(
            exc.code,
            exc.message,
            details={"trace": trace, "browser_failure": dict(exc.details)},
        ) from exc
    except Exception as exc:
        trace["browser_connect_seconds"] = round(time.monotonic() - connect_started, 3)
        message = normalize_text(str(exc)) or "Browser context creation failed."
        if not reused:
            _safe_close(browser_context)
            _safe_close(manager)
        raise PlaywrightBrowserFailure(
            BROWSER_CONTEXT_CREATE_FAILED,
            message,
            details={
                "trace": trace,
                "browser_failure": {
                    "stage": "browser_context_create",
                    "code": BROWSER_CONTEXT_CREATE_FAILED,
                    "message": message,
                },
            },
        ) from exc


def _ensure_browser_html_page(
    browser_context: Any,
    page: Any | None,
    *,
    manager: Any,
    shared_page_session: Any | None,
    trace: dict[str, Any],
) -> Any:
    if page is not None:
        return page
    try:
        page = browser_context.new_page()
        if shared_page_session is not None:
            shared_page_session.bind(
                manager=manager,
                context=browser_context,
                page=page,
            )
        return page
    except Exception as exc:
        message = normalize_text(str(exc)) or "Browser page creation failed."
        raise PlaywrightBrowserFailure(
            BROWSER_PAGE_CREATE_FAILED,
            message,
            details={
                "trace": trace,
                "browser_failure": {
                    "stage": "browser_page_create",
                    "code": BROWSER_PAGE_CREATE_FAILED,
                    "message": message,
                },
            },
        ) from exc


def _browser_route_timeout_ms(
    publisher: str,
    *,
    configured_timeout_ms: int,
) -> int:
    """Cap the caller budget with the catalog-compiled browser route timeout."""

    try:
        route_timeout_ms = (
            compile_route_execution_policy_for_kind(
                publisher,
                "html",
                prefer_transport="browser",
            ).timeout_seconds
            * 1000
        )
    except ValueError:
        # Unknown names are retained only for deterministic browser doubles;
        # the host guard still fails closed for real network origins.
        route_timeout_ms = configured_timeout_ms
    return min(configured_timeout_ms, route_timeout_ms)


def _prepare_browser_network_guard(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: PlaywrightRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None,
    remote_url_policy: SafeRemoteUrlPolicy | None,
    trace: dict[str, Any],
) -> tuple[BrowserNetworkGuard, list[str]]:
    # RFC 6761 ``.test`` origins are used by deterministic browser doubles.
    # They can pass syntax/allowlist checks, but any real request still fails
    # the interceptor's DNS/public-address validation.
    reserved_test_hosts = tuple(
        host
        for host in hosts_from_urls(candidate_urls)
        if host == "test" or host.endswith(".test")
    )
    allowed_hosts = tuple(
        dict.fromkeys(
            (*provider_allowed_hosts(publisher, "browser_html"), *reserved_test_hosts)
        )
    )
    if not allowed_hosts:
        raise PlaywrightBrowserFailure(
            "browser_network_policy_missing",
            f"No browser host allowlist is declared for provider {publisher!r}.",
        )
    network_guard = BrowserNetworkGuard(
        allowed_hosts=allowed_hosts,
        policy=remote_url_policy or SafeRemoteUrlPolicy(),
    )
    safe_candidate_urls: list[str] = []
    rejected_candidate_urls: list[dict[str, Any]] = []
    for raw_candidate_url in candidate_urls:
        normalized_candidate_url = normalize_text(raw_candidate_url)
        if not normalized_candidate_url:
            continue
        try:
            network_guard.validate(
                normalized_candidate_url,
                resolve_dns=True,
                enforce_credential_origin=False,
            )
        except Exception as exc:
            rejected_candidate_urls.append(
                {
                    **diagnostic_url_payload(normalized_candidate_url),
                    "error_type": exc.__class__.__name__,
                }
            )
            continue
        safe_candidate_urls.append(normalized_candidate_url)
    trace["network_policy_rejections"] = rejected_candidate_urls
    if not safe_candidate_urls:
        raise PlaywrightBrowserFailure(
            "unsafe_browser_url",
            "All browser candidates were rejected by the network safety policy.",
            details={"trace": trace},
        )
    credentialed_context = bool(
        list((browser_context_seed or {}).get("browser_cookies") or [])
        or config.storage_state_path
        or config.profile_dir
        or config.user_data_dir
    )
    if credentialed_context:
        credential_origin_url = (
            normalize_text(
                str((browser_context_seed or {}).get("browser_final_url") or "")
            )
            or safe_candidate_urls[0]
        )
        network_guard.set_credential_origin(credential_origin_url)
    return network_guard, safe_candidate_urls


def fetch_html_with_playwright(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: PlaywrightRuntimeConfig,
    wait_seconds: int = DEFAULT_BROWSER_RUNTIME_WAIT_SECONDS,
    max_timeout_ms: int | None = None,
    disable_media: bool = False,
    readiness: BrowserHtmlReadiness = DEFAULT_BROWSER_HTML_READINESS,
    runtime_context: RuntimeContext | None = None,
    browser_context_seed: Mapping[str, Any] | None = None,
    options: BrowserHtmlFetchOptions = DEFAULT_BROWSER_HTML_FETCH_OPTIONS,
    remote_url_policy: SafeRemoteUrlPolicy | None = None,
) -> BrowserFetchedHtml:
    return_image_payload = options.return_image_payload
    return_screenshot = options.return_screenshot
    lightweight_seed_only = options.lightweight_seed_only
    if not candidate_urls:
        raise PlaywrightBrowserFailure(
            "empty_html_attempts", "No publisher HTML candidates were attempted."
        )
    backend_name = normalize_text(config.backend).lower()
    active_blocked_resource_types = _active_browser_resource_types(
        backend_name=backend_name,
        disable_media=disable_media,
        options=options,
    )
    readiness_budget_seconds = options.readiness_budget_seconds
    reuse_runtime_page = options.reuse_runtime_page

    last_failure: PlaywrightBrowserFailure | None = None
    latest_browser_context_seed: Mapping[str, Any] | None = None
    caller_timeout_ms = (
        config.timeout_ms if max_timeout_ms is None else max(1, max_timeout_ms)
    )
    timeout_ms = _browser_route_timeout_ms(
        publisher,
        configured_timeout_ms=caller_timeout_ms,
    )
    if backend_name != "camoufox":
        raise PlaywrightBrowserFailure(
            "browser_backend_invalid",
            f"Unsupported browser backend {config.backend!r}.",
        )
    artifact_dir = config.artifact_dir / backend_name
    configured_user_agent = normalize_text(config.user_agent)
    normalized_wait_for_selector = normalize_text(readiness.selector)
    configured_storage_state_path = _storage_state_path(config)
    trace: dict[str, Any] = {
        "backend": backend_name,
        "candidate_count": len(candidate_urls),
        "candidates": [],
        "navigation_count": 0,
        "media_blocking": "media" in active_blocked_resource_types,
        "blocked_resource_types": sorted(active_blocked_resource_types),
        "blocked_request_count": 0,
        "blocked_request_types": [],
        "return_image_payload": bool(return_image_payload),
        "return_screenshot": bool(return_screenshot),
        "lightweight_seed_only": bool(lightweight_seed_only),
        "article_body_wait_enabled": bool(readiness.wait_for_article_body),
        "selector_wait_enabled": bool(normalized_wait_for_selector),
        "wait_for_selector": normalized_wait_for_selector or None,
        "external_cdp": bool(config.cdp_endpoint),
        "storage_state_path": str(configured_storage_state_path or ""),
        "storage_state_load": {
            "path": str(configured_storage_state_path or "") or None,
            "exists": bool(
                configured_storage_state_path is not None
                and configured_storage_state_path.is_file()
            ),
            "used": False,
        },
        "storage_state_write_enabled": config.persist_storage_state,
        "readiness_budget_seconds": readiness_budget_seconds,
        "runtime_page_reuse_enabled": bool(reuse_runtime_page),
    }
    overall_started = time.monotonic()
    local_deadline = overall_started + (timeout_ms / 1000.0)
    if runtime_context is not None and runtime_context.deadline_monotonic is not None:
        local_deadline = min(
            local_deadline,
            runtime_context.deadline_monotonic,
        )
    trace["timeout_budget_ms"] = timeout_ms
    readiness_deadline: float | None = None
    observed_blocked_resource_types: set[str] = set()
    network_guard, candidate_urls = _prepare_browser_network_guard(
        candidate_urls,
        publisher=publisher,
        config=config,
        browser_context_seed=browser_context_seed,
        remote_url_policy=remote_url_policy,
        trace=trace,
    )

    def remaining_timeout_ms() -> int:
        remaining = max(0.0, local_deadline - time.monotonic())
        if remaining <= 0:
            return 0
        return max(1, min(timeout_ms, int(remaining * 1000)))

    manager = None
    browser_context = None
    page = None
    shared_page_session = _runtime_figure_page_session(
        runtime_context,
        create=bool(reuse_runtime_page),
    )

    def route_after_validation(route: Any) -> None:
        resource_type = normalize_text(str(route.request.resource_type or "")).lower()
        if resource_type in active_blocked_resource_types:
            trace["blocked_request_count"] = (
                int(trace.get("blocked_request_count") or 0) + 1
            )
            observed_blocked_resource_types.add(resource_type)
            trace["blocked_request_types"] = sorted(observed_blocked_resource_types)
            route.abort()
            return
        route.continue_()

    try:
        _raise_if_cancelled(runtime_context)
        manager, browser_context, page = _open_browser_html_context(
            config,
            runtime_context=runtime_context,
            shared_page_session=shared_page_session,
            trace=trace,
        )
        storage_state_load = trace.get("storage_state_load")
        if isinstance(storage_state_load, dict):
            # Reused pages belong to a context opened with the same runtime config;
            # either way, reaching this point means the configured state was loaded.
            storage_state_load["used"] = bool(storage_state_load.get("exists"))
        try:
            network_guard.install_on_context(
                browser_context,
                after_validation=route_after_validation,
            )
        except Exception as exc:
            raise PlaywrightBrowserFailure(
                "browser_network_guard_install_failed",
                "Unable to install the browser network safety interceptor.",
                details={"trace": trace, "error_type": exc.__class__.__name__},
            ) from exc
        if trace.get("runtime_page_reused"):
            trace["browser_context_seed"] = {
                "provided": browser_context_seed is not None,
                "applied": False,
                "reason": "reused_runtime_page_context",
            }
        else:
            _seed_browser_html_context(
                browser_context,
                browser_context_seed=browser_context_seed,
                candidate_url=candidate_urls[0] if candidate_urls else None,
                trace=trace,
            )
        page = _ensure_browser_html_page(
            browser_context,
            page,
            manager=manager,
            shared_page_session=shared_page_session,
            trace=trace,
        )

        for url in candidate_urls:
            _raise_if_cancelled(runtime_context)
            candidate_timeout_ms = remaining_timeout_ms()
            if candidate_timeout_ms <= 0:
                trace["deadline_exhausted"] = True
                last_failure = _candidate_deadline_failure(
                    last_failure,
                    trace=trace,
                )
                break
            normalized_url = normalize_text(url)
            if not normalized_url:
                continue
            candidate_trace: dict[str, Any] = {
                **diagnostic_url_payload(normalized_url),
                "started_at": round(time.time(), 3),
                "remaining_before_ms": candidate_timeout_ms,
            }
            trace["candidates"].append(candidate_trace)
            candidate_started = time.monotonic()
            try:
                network_guard.validate(
                    normalized_url,
                    resolve_dns=True,
                )
                logger.debug(
                    "browser_request backend=%s provider=%s action=request wait_seconds=%s url=%s",
                    backend_name,
                    publisher,
                    wait_seconds,
                    candidate_trace.get("url"),
                )
                request_started = time.monotonic()
                trace["navigation_count"] = int(trace.get("navigation_count") or 0) + 1
                if shared_page_session is not None:
                    trace["runtime_page_navigation_count"] = (
                        shared_page_session.mark_navigation()
                    )
                response = _navigate_browser_page(
                    page,
                    url=normalized_url,
                    timeout_ms=candidate_timeout_ms,
                    return_image_payload=return_image_payload,
                )
                candidate_trace["navigation_seconds"] = round(
                    time.monotonic() - request_started, 3
                )
                if lightweight_seed_only:
                    final_url = (
                        normalize_text(str(getattr(page, "url", "") or ""))
                        or normalized_url
                    )
                    network_guard.validate(
                        final_url,
                        previous_url=normalized_url,
                        resolve_dns=True,
                    )
                    status = _browser_response_status(response, zero_as_none=False)
                    headers = _browser_response_headers(response)
                    candidate_trace["status"] = status
                    candidate_trace["final_url"] = diagnostic_url_payload(
                        final_url
                    ).get("url")
                    candidate_trace["final_url_sha256"] = diagnostic_url_payload(
                        final_url
                    ).get("url_sha256")
                    try:
                        html = str(page.content() or "")
                    except Exception:
                        html = ""
                    try:
                        title = normalize_text(str(page.title() or ""))
                    except Exception:
                        title = ""
                    summary = _browser_html_summary(publisher, html)
                    detected = detect_html_block(
                        title,
                        summary,
                        status,
                        html_text=html,
                        response_headers=headers,
                    )
                    browser_context_seed = _context_seed(
                        browser_context,
                        final_url=final_url,
                        user_agent=configured_user_agent
                        or browser_page_user_agent(page),
                        backend=backend_name,
                    )
                    browser_context_seed = merge_browser_context_seeds(
                        browser_context_seed,
                        {
                            "paper_fetch_html_fetcher": backend_name,
                            "diagnostics": {"browser_backend": backend_name},
                        },
                    )
                    candidate_trace["duration_seconds"] = round(
                        time.monotonic() - candidate_started, 3
                    )
                    rejection = _lightweight_seed_rejection(
                        status=status,
                        requested_url=normalized_url,
                        final_url=final_url,
                        detected=detected,
                    )
                    if rejection is not None:
                        reason, message = rejection
                        candidate_trace["result"] = "rejected"
                        candidate_trace["block_reason"] = reason
                        last_failure = _candidate_failure_outcome(
                            last_failure,
                            PlaywrightBrowserFailure(
                                reason,
                                message,
                                details={"trace": trace},
                            ),
                            trace=trace,
                        )
                        continue
                    if browser_context_seed.get(
                        "browser_cookies"
                    ) or browser_context_seed.get("browser_user_agent"):
                        latest_browser_context_seed = browser_context_seed
                    candidate_trace["result"] = "success"
                    trace["storage_state_save"] = {
                        "attempted": False,
                        "staged": False,
                        "saved": False,
                        "path": str(_storage_state_path(config) or "") or None,
                        "reason": "lightweight_navigation_not_accepted",
                    }
                    return BrowserFetchedHtml(
                        source_url=normalized_url,
                        final_url=final_url,
                        html="",
                        response_status=status,
                        response_headers=headers,
                        title=title or None,
                        summary=summary,
                        browser_context_seed=browser_context_seed,
                        diagnostics={"browser_runtime_trace": trace},
                    )
                if readiness_budget_seconds is not None and readiness_deadline is None:
                    # Readiness owns its own budget: browser startup and the first
                    # document navigation remain governed by the request deadline.
                    readiness_deadline = time.monotonic() + max(
                        0.0, float(readiness_budget_seconds)
                    )
                _wait_for_browser_html_readiness(
                    page,
                    publisher=publisher,
                    readiness=readiness,
                    wait_seconds=wait_seconds,
                    timeout_ms=candidate_timeout_ms,
                    request_started=request_started,
                    return_image_payload=return_image_payload,
                    runtime_context=runtime_context,
                    candidate_trace=candidate_trace,
                    readiness_timeout_seconds=(
                        max(0.0, readiness_deadline - time.monotonic())
                        if readiness_deadline is not None
                        else None
                    ),
                )
                _prepare_provider_browser_page(
                    page,
                    publisher=publisher,
                    timeout_ms=remaining_timeout_ms(),
                    candidate_trace=candidate_trace,
                )
                final_url = (
                    normalize_text(str(getattr(page, "url", "") or ""))
                    or normalized_url
                )
                network_guard.validate(
                    final_url,
                    previous_url=normalized_url,
                    resolve_dns=True,
                )
                html = str(page.content() or "")
                title = normalize_text(str(page.title() or ""))
                if not title and normalize_text(publisher).lower() != "ieee":
                    title = (
                        extract_page_title(BeautifulSoup(html, choose_parser())) or ""
                    )
                status = _browser_response_status(response, zero_as_none=False)
                headers = _browser_response_headers(response)
                candidate_trace["status"] = status
                candidate_trace["final_url"] = diagnostic_url_payload(final_url).get(
                    "url"
                )
                candidate_trace["final_url_sha256"] = diagnostic_url_payload(
                    final_url
                ).get("url_sha256")
                summary = _browser_html_summary(publisher, html)
                browser_context_seed = _context_seed(
                    browser_context,
                    final_url=final_url,
                    user_agent=configured_user_agent or browser_page_user_agent(page),
                    backend=backend_name,
                )
                browser_context_seed = merge_browser_context_seeds(
                    browser_context_seed,
                    {
                        "paper_fetch_html_fetcher": backend_name,
                        "diagnostics": {"browser_backend": backend_name},
                    },
                )
                if browser_context_seed.get(
                    "browser_cookies"
                ) or browser_context_seed.get("browser_user_agent"):
                    latest_browser_context_seed = browser_context_seed
                image_payload = None
                if return_image_payload:
                    try:
                        image_payload = _capture_image_payload(
                            page,
                            request_url=normalized_url,
                            final_url=final_url,
                        )
                        if image_payload is not None:
                            network_guard.validate(
                                normalize_text(str(image_payload.get("url") or "")),
                                previous_url=normalized_url,
                                resolve_dns=True,
                            )
                    except Exception:
                        image_payload = None
                    image_failure = getattr(page, _IMAGE_PAYLOAD_FAILURE_ATTR, None)
                    if isinstance(image_failure, Mapping):
                        headers = dict(headers)
                        headers["x-paper-fetch-image-payload-failure-reason"] = (
                            normalize_text(str(image_failure.get("reason") or ""))
                        )
            except RequestCancelledError:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started,
                    3,
                )
                candidate_trace["error"] = "cancelled"
                raise
            except Exception as exc:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started,
                    3,
                )
                candidate_trace["error"] = (
                    normalize_text(str(exc)) or exc.__class__.__name__
                )
                if isinstance(exc, PlaywrightBrowserFailure):
                    candidate_failure = exc
                else:
                    candidate_failure = PlaywrightBrowserFailure(
                        f"{backend_name}_request_failed",
                        normalize_text(str(exc))
                        or f"{backend_name} page request failed.",
                        details={"trace": trace},
                    )
                last_failure = _candidate_failure_outcome(
                    last_failure,
                    candidate_failure,
                    trace=trace,
                )
                continue

            if looks_like_abstract_redirect(normalized_url, final_url):
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = REDIRECTED_TO_ABSTRACT
                last_failure = _candidate_failure_outcome(
                    last_failure,
                    PlaywrightBrowserFailure(
                        REDIRECTED_TO_ABSTRACT,
                        "Publisher redirected the full-text URL to an abstract page.",
                        browser_context_seed=browser_context_seed,
                        details={"trace": trace},
                    ),
                    trace=trace,
                )
                continue

            required_selector_ready = bool(
                readiness.require_selector
                and candidate_trace.get("selector_readiness_ready")
            )
            # Stable provider body readiness outweighs navigation-only access
            # labels; challenge and explicit HTTP failures still fail closed.
            substantive_body_ready = bool(
                readiness.wait_for_article_body
                and candidate_trace.get("dom_readiness_ready")
            )
            detected = detect_html_block(
                title or "",
                summary,
                status,
                substantive_body_ready=substantive_body_ready,
                html_text="" if required_selector_ready else html,
                response_headers={} if required_selector_ready else headers,
            )
            if detected is not None and not return_image_payload:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = detected.reason
                last_failure = _candidate_failure_outcome(
                    last_failure,
                    PlaywrightBrowserFailure(
                        detected.reason,
                        detected.message,
                        browser_context_seed=browser_context_seed,
                        details=_browser_page_failure_details(
                            trace=trace,
                            runtime_context=runtime_context,
                            request=PageDiagnosticRequest(
                                provider=publisher,
                                route="browser_html",
                                attempt=max(
                                    1, len(list(trace.get("candidates") or []))
                                ),
                                failure_code=detected.reason,
                                stage="block_detection",
                                html_text=html,
                                doi=config.doi,
                                target_url=normalized_url,
                                final_url=final_url,
                                backend=config.backend,
                                response_status=status,
                                title=title or "",
                                summary=summary,
                                details={"browser_runtime_trace": dict(trace)},
                            ),
                        ),
                    ),
                    trace=trace,
                )
                continue
            if (
                readiness.require_selector
                and not return_image_payload
                and not bool(candidate_trace.get("selector_readiness_ready"))
            ):
                reason = "browser_article_not_ready"
                message = (
                    "Publisher browser page did not expose the required article "
                    "container before the readiness timeout."
                )
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = reason
                last_failure = _candidate_failure_outcome(
                    last_failure,
                    PlaywrightBrowserFailure(
                        reason,
                        message,
                        browser_context_seed=browser_context_seed,
                        details=_browser_page_failure_details(
                            trace=trace,
                            runtime_context=runtime_context,
                            request=PageDiagnosticRequest(
                                provider=publisher,
                                route="browser_html",
                                attempt=max(
                                    1, len(list(trace.get("candidates") or []))
                                ),
                                failure_code=reason,
                                stage="dom_readiness",
                                html_text=html,
                                doi=config.doi,
                                target_url=normalized_url,
                                final_url=final_url,
                                backend=config.backend,
                                response_status=status,
                                title=title or "",
                                summary=summary,
                                details={"browser_runtime_trace": dict(trace)},
                            ),
                        ),
                    ),
                    trace=trace,
                )
                continue
            if not normalize_text(html) and image_payload is None:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = "empty_html_response"
                last_failure = _candidate_failure_outcome(
                    last_failure,
                    PlaywrightBrowserFailure(
                        "empty_html_response",
                        f"{backend_name} returned empty publisher HTML.",
                        browser_context_seed=browser_context_seed,
                        details={"trace": trace},
                    ),
                    trace=trace,
                )
                continue

            screenshot_b64 = _capture_page_screenshot(
                page,
                enabled=return_screenshot,
                timeout_provider=remaining_timeout_ms,
            )
            candidate_trace["duration_seconds"] = round(
                time.monotonic() - candidate_started, 3
            )
            candidate_trace["result"] = "success"
            staged_storage_state = None
            if config.persist_storage_state and not return_image_payload:
                staged_storage_state, storage_state_result = _stage_storage_state(
                    browser_context,
                    config,
                    filter_url=final_url,
                )
                trace["storage_state_save"] = storage_state_result
            else:
                trace["storage_state_save"] = {
                    "attempted": False,
                    "staged": False,
                    "saved": False,
                    "path": str(_storage_state_path(config) or "") or None,
                    "reason": (
                        "non_article_payload"
                        if return_image_payload
                        else "storage_state_write_disabled"
                    ),
                }
            return BrowserFetchedHtml(
                source_url=normalized_url,
                final_url=final_url,
                html=html,
                response_status=status,
                response_headers=headers,
                title=title,
                summary=summary,
                browser_context_seed=browser_context_seed,
                screenshot_b64=screenshot_b64,
                image_payload=image_payload,
                diagnostics={"browser_runtime_trace": trace},
                staged_storage_state=staged_storage_state,
            )
    finally:
        if "storage_state_save" not in trace:
            trace["storage_state_save"] = {
                "attempted": False,
                "staged": False,
                "saved": False,
                "path": str(_storage_state_path(config) or "") or None,
                "reason": (
                    "provider_acceptance_not_reached"
                    if config.persist_storage_state
                    else "storage_state_write_disabled"
                ),
            }
        trace["duration_seconds"] = round(time.monotonic() - overall_started, 3)
        trace["remaining_ms"] = remaining_timeout_ms()
        if runtime_context is not None and hasattr(
            runtime_context, "accumulate_stage_timing"
        ):
            with contextlib.suppress(Exception):
                runtime_context.accumulate_stage_timing(
                    "browser_seconds",
                    elapsed=time.monotonic() - overall_started,
                )
        if (
            shared_page_session is None
            or shared_page_session.context is not browser_context
        ):
            _safe_close(page)
            _safe_close(browser_context)
            _safe_close(manager)

    if last_failure is None and latest_browser_context_seed is not None:
        last_failure = PlaywrightBrowserFailure(
            "empty_html_attempts",
            "No publisher HTML candidates were attempted.",
            browser_context_seed=latest_browser_context_seed,
            details={"trace": trace},
        )
    if last_failure is None:
        last_failure = PlaywrightBrowserFailure(
            "empty_html_attempts",
            "No publisher HTML candidates were attempted.",
            details={"trace": trace},
        )
    if artifact_dir:
        with contextlib.suppress(OSError):
            artifact_dir.mkdir(parents=True, exist_ok=True)
    raise last_failure


fetch_html_with_playwright.paper_fetch_html_fetcher_name = "camoufox"  # type: ignore[attr-defined]


def fetch_html_with_playwright_fast(*args: Any, **kwargs: Any) -> BrowserFetchedHtml:
    return fetch_html_with_playwright(*args, **kwargs)


fetch_html_with_playwright_fast.paper_fetch_html_fetcher_name = "camoufox_fast"  # type: ignore[attr-defined]


def warm_browser_context_with_playwright(
    candidate_urls: list[str],
    *,
    publisher: str,
    config: PlaywrightRuntimeConfig,
    browser_context_seed: Mapping[str, Any] | None = None,
    runtime_context: RuntimeContext | None = None,
    lightweight: bool = False,
) -> BrowserWarmResult:
    merged_seed = merge_browser_context_seeds(browser_context_seed)
    if not candidate_urls:
        return BrowserWarmResult(
            seed=merged_seed,
            changed=False,
            accepted=False,
            status=None,
            reason="empty_warm_candidates",
        )

    try:
        result = fetch_html_with_playwright(
            candidate_urls,
            publisher=publisher,
            config=config,
            browser_context_seed=merged_seed,
            runtime_context=runtime_context,
            options=BrowserHtmlFetchOptions(lightweight_seed_only=lightweight),
        )
    except PlaywrightBrowserFailure as exc:
        trace = exc.details.get("trace")
        status = None
        if isinstance(trace, Mapping):
            candidates = trace.get("candidates")
            if isinstance(candidates, list) and candidates:
                candidate = candidates[-1]
                if isinstance(candidate, Mapping):
                    status = _safe_int(candidate.get("status"), default=0) or None
        return BrowserWarmResult(
            seed=merged_seed,
            changed=False,
            accepted=False,
            status=status,
            reason=exc.kind,
            final_url=normalize_text(
                str((exc.browser_context_seed or {}).get("browser_final_url") or "")
            )
            or None,
            diagnostics=dict(exc.details),
        )
    refreshed_seed = merge_browser_context_seeds(
        merged_seed, result.browser_context_seed
    )
    delta = _cookie_delta(merged_seed, refreshed_seed)
    changed = any(delta.values())
    return BrowserWarmResult(
        seed=refreshed_seed,
        changed=changed,
        accepted=True,
        status=result.response_status,
        reason="refreshed" if changed else "no_cookie_change",
        final_url=result.final_url,
        cookie_delta=delta,
        diagnostics=dict(result.diagnostics or {}),
    )
