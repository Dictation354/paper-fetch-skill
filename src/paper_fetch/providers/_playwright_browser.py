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
from ..extraction.image_payloads import (
    image_dimensions_from_bytes,
    image_mime_type_from_bytes,
)
from ..http import RequestCancelledError, diagnostic_url_payload
from ..page_diagnostics import PageDiagnosticRequest, capture_page_diagnostic
from ..quality.html_availability import choose_parser, extract_page_title
from ..quality.html_signals import looks_like_abstract_redirect
from ..quality.reason_codes import REDIRECTED_TO_ABSTRACT
from ..reason_codes import (
    BROWSER_CONTEXT_CREATE_FAILED,
    BROWSER_PAGE_CREATE_FAILED,
)
from ..runtime_browser import (
    ManagedBrowserError,
    browser_page_user_agent,
)
from ..utils import normalize_text
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
)
from .browser_workflow.fetchers.readiness import (
    BodyDomReadinessResult,
    wait_for_atypon_body_dom_ready,
)
from .browser_workflow.fetchers.scripts import _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT
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
DEFAULT_BROWSER_HTML_READINESS = BrowserHtmlReadiness()
DEFAULT_BROWSER_HTML_FETCH_OPTIONS = BrowserHtmlFetchOptions()
_IMAGE_PAYLOAD_MIN_IMAGE_DIMENSION = 1
_IMAGE_RESPONSE_BLOCKED_BY_HTML_WRAPPER = "image_response_blocked_by_html_wrapper"
_IMAGE_PAYLOAD_RESPONSE_ATTR = "_paper_fetch_top_level_response"
_IMAGE_PAYLOAD_TIMEOUT_ATTR = "_paper_fetch_image_payload_timeout_ms"
_IMAGE_PAYLOAD_FAILURE_ATTR = "_paper_fetch_image_payload_failure"
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


def _response_body(response: Any) -> bytes | None:
    if response is None:
        return None
    try:
        body = response.body()
    except Exception:
        return None
    if not isinstance(body, (bytes, bytearray)) or not body:
        return None
    return bytes(body)


def _browser_image_payload_from_bytes(
    body: bytes | bytearray | None,
    *,
    content_type: str | None,
    url: str,
    status: int | None,
    width: int = 0,
    height: int = 0,
) -> BrowserImagePayload | None:
    if not isinstance(body, (bytes, bytearray)) or not body:
        return None
    payload_body = bytes(body)
    detected_type = image_mime_type_from_bytes(payload_body)
    if not detected_type:
        return None
    normalized_content_type = _normalized_content_type(content_type) or detected_type
    if not normalized_content_type.startswith("image/"):
        normalized_content_type = detected_type
    dimensions = image_dimensions_from_bytes(payload_body)
    if dimensions is not None:
        width = width or dimensions[0]
        height = height or dimensions[1]
    return {
        "bodyB64": base64.b64encode(payload_body).decode("ascii"),
        "contentType": normalized_content_type,
        "url": normalize_text(url),
        "status": status or 200,
        "width": max(0, _safe_int(width)),
        "height": max(0, _safe_int(height)),
    }


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


def _image_element_has_loaded_natural_size(image_element: Any) -> bool | None:
    try:
        image_info = image_element.evaluate(
            """
            (image) => ({
              width: image.naturalWidth || 0,
              height: image.naturalHeight || 0,
              complete: !!image.complete,
            })
            """
        )
    except Exception:
        return None
    if not isinstance(image_info, Mapping):
        return None
    return (
        bool(image_info.get("complete", True))
        and _safe_int(image_info.get("width")) > 0
        and _safe_int(image_info.get("height")) > 0
    )


def _payload_from_canvas_export(
    rendered: Any,
    *,
    fallback_url: str,
    status: int | None,
) -> BrowserImagePayload | None:
    if not isinstance(rendered, Mapping) or not rendered.get("ok"):
        return None
    body_b64 = normalize_text(str(rendered.get("bodyB64") or ""))
    content_type = (
        _normalized_content_type(str(rendered.get("contentType") or "")) or "image/png"
    )
    data_url = normalize_text(
        str(rendered.get("dataURL") or rendered.get("dataUrl") or "")
    )
    if data_url.startswith("data:") and "," in data_url:
        metadata, body_b64 = data_url.split(",", 1)
        content_type = (
            _normalized_content_type(metadata.removeprefix("data:").split(";", 1)[0])
            or content_type
        )
    try:
        body = base64.b64decode(body_b64, validate=True)
    except Exception:
        return None
    return _browser_image_payload_from_bytes(
        body,
        content_type=content_type,
        url=fallback_url,
        status=status,
        width=_safe_int(rendered.get("width")),
        height=_safe_int(rendered.get("height")),
    )


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

    if content_type.startswith("image/"):
        payload = _browser_image_payload_from_bytes(
            _response_body(response),
            content_type=content_type,
            url=normalized_final_url,
            status=status,
        )
        if payload is not None:
            return payload

    html = ""
    try:
        html = str(page.content() or "")
    except Exception:
        html = ""
    if _normalized_content_type(content_type) in {
        "image/svg+xml",
        "",
    } or normalize_text(html).startswith("<"):
        svg_payload = _browser_image_payload_from_bytes(
            html.encode("utf-8"),
            content_type="image/svg+xml",
            url=normalized_final_url,
            status=status,
        )
        if svg_payload is not None and svg_payload["contentType"] == "image/svg+xml":
            return svg_payload

    image_element = None
    try:
        image_element = page.query_selector("img")
    except Exception:
        image_element = None
    if image_element is not None:
        loaded = _image_element_has_loaded_natural_size(image_element)
        if loaded is not False:
            try:
                rendered = page.evaluate(
                    _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
                    [
                        normalized_request_url,
                        _IMAGE_PAYLOAD_MIN_IMAGE_DIMENSION,
                        _IMAGE_PAYLOAD_MIN_IMAGE_DIMENSION,
                    ],
                )
            except Exception:
                rendered = None
            payload = _payload_from_canvas_export(
                rendered,
                fallback_url=normalized_final_url,
                status=status,
            )
            if payload is not None:
                return payload

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
        body_readiness = wait_for_atypon_body_dom_ready(
            page,
            publisher,
            timeout_seconds=min(
                max(float(wait_seconds), 20.0),
                remaining_timeout_seconds,
            ),
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
        selector_timeout_ms = min(
            max(1, int(wait_seconds) * 1000),
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
        if remaining_wait_ms > 0:
            page.wait_for_timeout(
                min(max(0, int(wait_seconds)) * 1000, remaining_wait_ms)
            )
        _raise_if_cancelled(runtime_context)
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


def _browser_html_summary(publisher: str, html_text: str) -> str:
    if normalize_text(publisher).lower() == "ieee":
        return summarize_visible_html(html_text)
    return summarize_html(html_text)


def _browser_page_failure_details(
    *,
    reason: str,
    trace: Mapping[str, Any],
    runtime_context: RuntimeContext | None,
    publisher: str,
    config: BrowserRuntimeConfig,
    target_url: str,
    final_url: str,
    html_text: str,
    status: int | None,
    title: str,
    summary: str,
    stage: str,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "trace": dict(trace),
        "stage": stage,
        "final_url": diagnostic_url_payload(final_url),
        "response_status": status,
        "title_summary": title[:500] or None,
        "page_summary": summary[:1000] or None,
    }
    if reason == "aws_waf_challenge":
        details.update(
            {
                "challenge_provider": "aws_waf",
                "legacy_reason_code": "cloudflare_challenge",
            }
        )
    if runtime_context is None:
        return details
    diagnostic = capture_page_diagnostic(
        runtime_context,
        PageDiagnosticRequest(
            provider=publisher,
            route="browser_html",
            attempt=max(1, len(list(trace.get("candidates") or []))),
            failure_code=reason,
            stage=stage,
            html_text=html_text,
            doi=config.doi,
            target_url=target_url,
            final_url=final_url,
            backend=config.backend,
            response_status=status,
            title=title,
            summary=summary,
            details={"browser_runtime_trace": dict(trace)},
        ),
    )
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
) -> BrowserFetchedHtml:
    return_image_payload = options.return_image_payload
    return_screenshot = options.return_screenshot
    lightweight_seed_only = options.lightweight_seed_only
    if not candidate_urls:
        raise PlaywrightBrowserFailure(
            "empty_html_attempts", "No publisher HTML candidates were attempted."
        )
    if return_image_payload:
        disable_media = False

    last_failure: PlaywrightBrowserFailure | None = None
    latest_browser_context_seed: Mapping[str, Any] | None = None
    timeout_ms = config.timeout_ms if max_timeout_ms is None else max(1, max_timeout_ms)
    backend_name = normalize_text(config.backend).lower()
    if backend_name != "camoufox":
        raise PlaywrightBrowserFailure(
            "browser_backend_invalid",
            f"Unsupported browser backend {config.backend!r}.",
        )
    artifact_dir = config.artifact_dir / backend_name
    configured_user_agent = normalize_text(config.user_agent)
    normalized_wait_for_selector = normalize_text(readiness.selector)
    trace: dict[str, Any] = {
        "backend": backend_name,
        "candidate_count": len(candidate_urls),
        "candidates": [],
        "media_blocking": bool(disable_media),
        "return_image_payload": bool(return_image_payload),
        "return_screenshot": bool(return_screenshot),
        "lightweight_seed_only": bool(lightweight_seed_only),
        "article_body_wait_enabled": bool(readiness.wait_for_article_body),
        "selector_wait_enabled": bool(normalized_wait_for_selector),
        "wait_for_selector": normalized_wait_for_selector or None,
        "external_cdp": bool(config.cdp_endpoint),
        "storage_state_path": str(_storage_state_path(config) or ""),
        "storage_state_write_enabled": config.persist_storage_state,
    }
    overall_started = time.monotonic()
    local_deadline = overall_started + (timeout_ms / 1000.0)
    if runtime_context is not None and runtime_context.deadline_monotonic is not None:
        local_deadline = min(
            local_deadline,
            runtime_context.deadline_monotonic,
        )
    trace["timeout_budget_ms"] = timeout_ms

    def remaining_timeout_ms() -> int:
        remaining = max(0.0, local_deadline - time.monotonic())
        if remaining <= 0:
            return 0
        return max(1, min(timeout_ms, int(remaining * 1000)))

    manager = None
    browser_context = None
    page = None
    try:
        _raise_if_cancelled(runtime_context)
        try:
            connect_started = time.monotonic()
            manager, browser_context = open_browser_context(
                config,
                runtime_context=runtime_context,
            )
            connect_seconds = round(time.monotonic() - connect_started, 3)
            trace["browser_connect_seconds"] = connect_seconds
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
            _seed_browser_html_context(
                browser_context,
                browser_context_seed=browser_context_seed,
                candidate_url=candidate_urls[0] if candidate_urls else None,
                trace=trace,
            )
        except PlaywrightBrowserFailure:
            raise
        except ManagedBrowserError as exc:
            trace["browser_connect_seconds"] = round(
                time.monotonic() - connect_started, 3
            )
            trace["browser_failure"] = dict(exc.details)
            raise PlaywrightBrowserFailure(
                exc.code,
                exc.message,
                details={"trace": trace, "browser_failure": dict(exc.details)},
            ) from exc
        except Exception as exc:
            trace["browser_connect_seconds"] = round(
                time.monotonic() - connect_started, 3
            )
            message = normalize_text(str(exc)) or "Browser context creation failed."
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

        try:
            page = browser_context.new_page()
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

        def route_handler(route: Any) -> None:
            try:
                resource_type = normalize_text(
                    str(route.request.resource_type or "")
                ).lower()
                blocked_types = (
                    {"media"}
                    if backend_name == "camoufox"
                    else BROWSER_HTML_BLOCKED_RESOURCE_TYPES
                )
                if disable_media and resource_type in blocked_types:
                    route.abort()
                    return
                route.continue_()
            except Exception:
                with contextlib.suppress(Exception):
                    route.continue_()

        if disable_media:
            with contextlib.suppress(Exception):
                page.route("**/*", route_handler)

        for url in candidate_urls:
            _raise_if_cancelled(runtime_context)
            candidate_timeout_ms = remaining_timeout_ms()
            if candidate_timeout_ms <= 0:
                trace["deadline_exhausted"] = True
                last_failure = PlaywrightBrowserFailure(
                    "browser_connect_timeout",
                    "Browser HTML request deadline was exhausted before another candidate.",
                    details={"trace": trace},
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
                logger.debug(
                    "browser_request backend=%s provider=%s action=request wait_seconds=%s url=%s",
                    backend_name,
                    publisher,
                    wait_seconds,
                    candidate_trace.get("url"),
                )
                request_started = time.monotonic()
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
                        last_failure = PlaywrightBrowserFailure(
                            reason,
                            message,
                            details={"trace": trace},
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
                )
                final_url = (
                    normalize_text(str(getattr(page, "url", "") or ""))
                    or normalized_url
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
                    last_failure = exc
                else:
                    last_failure = PlaywrightBrowserFailure(
                        f"{backend_name}_request_failed",
                        normalize_text(str(exc))
                        or f"{backend_name} page request failed.",
                        details={"trace": trace},
                    )
                continue

            if looks_like_abstract_redirect(normalized_url, final_url):
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = REDIRECTED_TO_ABSTRACT
                last_failure = PlaywrightBrowserFailure(
                    REDIRECTED_TO_ABSTRACT,
                    "Publisher redirected the full-text URL to an abstract page.",
                    browser_context_seed=browser_context_seed,
                    details={"trace": trace},
                )
                continue

            required_selector_ready = bool(
                readiness.require_selector
                and candidate_trace.get("selector_readiness_ready")
            )
            detected = detect_html_block(
                title or "",
                summary,
                status,
                html_text="" if required_selector_ready else html,
                response_headers={} if required_selector_ready else headers,
            )
            if detected is not None and not return_image_payload:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = detected.reason
                last_failure = PlaywrightBrowserFailure(
                    detected.reason,
                    detected.message,
                    browser_context_seed=browser_context_seed,
                    details=_browser_page_failure_details(
                        reason=detected.reason,
                        trace=trace,
                        runtime_context=runtime_context,
                        publisher=publisher,
                        config=config,
                        target_url=normalized_url,
                        final_url=final_url,
                        html_text=html,
                        status=status,
                        title=title or "",
                        summary=summary,
                        stage="block_detection",
                    ),
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
                last_failure = PlaywrightBrowserFailure(
                    reason,
                    message,
                    browser_context_seed=browser_context_seed,
                    details=_browser_page_failure_details(
                        reason=reason,
                        trace=trace,
                        runtime_context=runtime_context,
                        publisher=publisher,
                        config=config,
                        target_url=normalized_url,
                        final_url=final_url,
                        html_text=html,
                        status=status,
                        title=title or "",
                        summary=summary,
                        stage="dom_readiness",
                    ),
                )
                continue
            if not normalize_text(html) and image_payload is None:
                candidate_trace["duration_seconds"] = round(
                    time.monotonic() - candidate_started, 3
                )
                candidate_trace["block_reason"] = "empty_html_response"
                last_failure = PlaywrightBrowserFailure(
                    "empty_html_response",
                    f"{backend_name} returned empty publisher HTML.",
                    browser_context_seed=browser_context_seed,
                    details={"trace": trace},
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
