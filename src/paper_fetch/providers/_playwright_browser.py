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
    RequestCancelledError,
    diagnostic_url_payload,
    redact_text_for_diagnostics,
)
from ..page_diagnostics import PageDiagnosticRequest, capture_page_diagnostic
from ..provider_catalog import compile_route_execution_policy_for_kind
from ..publisher_identity import extract_doi, extract_doi_from_url, normalize_doi
from ..quality.html_availability import (
    HtmlQualityAssessor,
    choose_parser,
    extract_page_title,
)
from ..quality.html_signals import looks_like_abstract_redirect
from ..reason_codes import (
    ABSTRACT_ONLY,
    AWS_WAF_CHALLENGE,
    BROWSER_CONTEXT_CREATE_FAILED,
    BROWSER_PAGE_CREATE_FAILED,
    CLOUDFLARE_CHALLENGE,
    PUBLISHER_ACCESS_DENIED,
    PUBLISHER_PAYWALL,
    REDIRECTED_TO_ABSTRACT,
)
from ..runtime_browser import browser_page_user_agent
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
MAX_BROWSER_SCREENSHOT_BYTES = 16 * 1024 * 1024
MAX_BROWSER_DIAGNOSTIC_EVENTS = 8
MAX_BROWSER_DIAGNOSTIC_TEXT_CHARS = 500
DEFAULT_BROWSER_HTML_READINESS = BrowserHtmlReadiness()
DEFAULT_BROWSER_HTML_FETCH_OPTIONS = BrowserHtmlFetchOptions()
_IMAGE_RESPONSE_BLOCKED_BY_HTML_WRAPPER = "image_response_blocked_by_html_wrapper"
_IMAGE_PAYLOAD_RESPONSE_ATTR = "_paper_fetch_top_level_response"
_IMAGE_PAYLOAD_TIMEOUT_ATTR = "_paper_fetch_image_payload_timeout_ms"
_IMAGE_PAYLOAD_FAILURE_ATTR = "_paper_fetch_image_payload_failure"
_HTTP_ACCESS_STATUS_REVIEW_KEY = "http_access_status_review"
_WILEY_REVIEWABLE_HTTP_STATUSES = frozenset({401, 403})
_WILEY_DOI_META_NAMES = frozenset(
    {"citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi"}
)
_MAIN_DOCUMENT_NAVIGATION_DIAGNOSTIC_SCRIPT = """
() => {
  const entry = performance.getEntriesByType('navigation')[0] || null;
  const finite = (value) => Number.isFinite(value) ? value : null;
  return {
    documentReadyState: String(document.readyState || ''),
    navigation: entry ? {
      type: String(entry.type || ''),
      nextHopProtocol: String(entry.nextHopProtocol || ''),
      responseStart: finite(entry.responseStart),
      responseEnd: finite(entry.responseEnd),
      domInteractive: finite(entry.domInteractive),
      domContentLoadedEventEnd: finite(entry.domContentLoadedEventEnd),
      loadEventEnd: finite(entry.loadEventEnd),
      duration: finite(entry.duration),
      transferSize: finite(entry.transferSize),
      encodedBodySize: finite(entry.encodedBodySize),
      decodedBodySize: finite(entry.decodedBodySize),
    } : null,
  };
}
"""
_IMAGE_ARRAY_BUFFER_EXPORT_SCRIPT = """
async ([targetUrl]) => {
  const bytesToBase64 = (bytes) => {
    const chunkSize = 0x8000;
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
    }
    return btoa(binary);
  };
  try {
    const response = await fetch(targetUrl, {
      credentials: 'include',
      cache: 'no-store',
    });
    const buffer = await response.arrayBuffer();
    return {
      ok: response.ok,
      status: response.status,
      url: response.url || targetUrl,
      contentType: response.headers.get('content-type') || '',
      bodyB64: bytesToBase64(new Uint8Array(buffer)),
    };
  } catch (error) {
    return {
      ok: false,
      reason: 'browser_array_buffer_failed',
      error: String((error && (error.name || error.message)) || error || ''),
    };
  }
}
"""
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


def _diagnostic_event_value(value: Any) -> Any:
    try:
        return value() if callable(value) else value
    except Exception:
        return None


def _diagnostic_event_attr(value: Any, name: str) -> Any:
    try:
        return _diagnostic_event_value(getattr(value, name, None))
    except Exception:
        return None


def _bounded_diagnostic_text(value: Any) -> str:
    return redact_text_for_diagnostics(str(value or ""))[
        :MAX_BROWSER_DIAGNOSTIC_TEXT_CHARS
    ]


def _append_bounded_event(target: list[dict[str, Any]], value: dict[str, Any]) -> None:
    if len(target) < MAX_BROWSER_DIAGNOSTIC_EVENTS:
        target.append(value)


def _install_page_diagnostic_listeners(
    page: Any,
    trace: dict[str, Any],
) -> tuple[
    list[tuple[str, Callable[[Any], None]]],
    dict[int, tuple[dict[str, Any], float]],
]:
    """Collect a small, secret-safe summary of browser failures."""

    events: dict[str, list[dict[str, Any]]] = {
        "document_requests": [],
        "failed_requests": [],
        "failed_scripts": [],
        "console_errors": [],
        "page_errors": [],
    }
    trace["page_events"] = events
    document_requests: dict[int, tuple[dict[str, Any], float]] = {}

    def document_request_record(
        request: Any,
    ) -> tuple[dict[str, Any], float] | None:
        resource_type = normalize_text(
            str(_diagnostic_event_attr(request, "resource_type") or "")
        ).lower()
        if resource_type != "document":
            return None
        request_key = id(request)
        existing = document_requests.get(request_key)
        if existing is not None:
            return existing
        if len(document_requests) >= MAX_BROWSER_DIAGNOSTIC_EVENTS:
            return None
        url = normalize_text(str(_diagnostic_event_attr(request, "url") or ""))
        record: dict[str, Any] = {
            **diagnostic_url_payload(url),
            "resource_type": "document",
            "response_received_observed": False,
            "request_finished_observed": False,
            "request_failed_observed": False,
        }
        started_at = time.monotonic()
        document_requests[request_key] = (record, started_at)
        _append_bounded_event(events["document_requests"], record)
        return record, started_at

    def request_started(request: Any) -> None:
        document_request_record(request)

    def response_received(response: Any) -> None:
        request = _diagnostic_event_attr(response, "request")
        tracked = document_request_record(request)
        if tracked is None:
            return
        record, started_at = tracked
        headers = _browser_response_headers(response)
        record.update(
            {
                "response_received_observed": True,
                "response_received_ms": round(
                    max(0.0, time.monotonic() - started_at) * 1000,
                    3,
                ),
                "status": _browser_response_status(response, zero_as_none=False),
                "content_type": (
                    _normalized_content_type(headers.get("content-type")) or None
                ),
                "content_length_bytes": _content_length_diagnostic(headers),
                "transfer_encoding_present": bool(
                    normalize_text(headers.get("transfer-encoding"))
                ),
                "chunked_transfer_declared": (
                    "chunked"
                    in normalize_text(headers.get("transfer-encoding")).lower()
                ),
            }
        )

    def request_finished(request: Any) -> None:
        tracked = document_request_record(request)
        if tracked is None:
            return
        record, started_at = tracked
        record.update(
            {
                "request_finished_observed": True,
                "request_finished_ms": round(
                    max(0.0, time.monotonic() - started_at) * 1000,
                    3,
                ),
            }
        )

    def request_failed(request: Any) -> None:
        resource_type = normalize_text(
            str(_diagnostic_event_attr(request, "resource_type") or "")
        ).lower()
        url = normalize_text(str(_diagnostic_event_attr(request, "url") or ""))
        failure = _diagnostic_event_attr(request, "failure")
        summary = {
            **diagnostic_url_payload(url),
            "resource_type": resource_type or None,
            "error": _bounded_diagnostic_text(failure) or None,
        }
        _append_bounded_event(events["failed_requests"], summary)
        if resource_type == "script":
            _append_bounded_event(events["failed_scripts"], summary)
        tracked = document_request_record(request)
        if tracked is not None:
            record, started_at = tracked
            record.update(
                {
                    "request_failed_observed": True,
                    "request_failure": _bounded_diagnostic_text(failure) or None,
                    "request_failed_ms": round(
                        max(0.0, time.monotonic() - started_at) * 1000,
                        3,
                    ),
                }
            )

    def console_message(message: Any) -> None:
        message_type = normalize_text(
            str(_diagnostic_event_value(getattr(message, "type", "")) or "")
        ).lower()
        if message_type != "error":
            return
        text = _diagnostic_event_value(getattr(message, "text", ""))
        _append_bounded_event(
            events["console_errors"],
            {"type": "error", "message": _bounded_diagnostic_text(text)},
        )

    def page_error(error: Any) -> None:
        _append_bounded_event(
            events["page_errors"],
            {
                "error_type": type(error).__name__,
                "message": _bounded_diagnostic_text(error),
            },
        )

    listeners: list[tuple[str, Callable[[Any], None]]] = [
        ("request", request_started),
        ("response", response_received),
        ("requestfinished", request_finished),
        ("requestfailed", request_failed),
        ("console", console_message),
        ("pageerror", page_error),
    ]
    on = getattr(page, "on", None)
    if callable(on):
        for event, callback in listeners:
            with contextlib.suppress(Exception):
                on(event, callback)
    return listeners, document_requests


def _remove_page_diagnostic_listeners(
    page: Any,
    listeners: list[tuple[str, Callable[[Any], None]]],
) -> None:
    remove = getattr(page, "remove_listener", None)
    if not callable(remove):
        remove = getattr(page, "off", None)
    if not callable(remove):
        return
    for event, callback in listeners:
        with contextlib.suppress(Exception):
            remove(event, callback)


def _main_document_response_diagnostic(
    response: Any,
    *,
    page: Any,
    fallback_url: str,
    status: int | None,
    headers: Mapping[str, str],
    document_requests: Mapping[int, tuple[Mapping[str, Any], float]],
    captured_html_bytes: int | None = None,
) -> dict[str, Any]:
    response_url = normalize_text(
        str(_diagnostic_event_attr(response, "url") or "")
    ) or normalize_text(fallback_url)
    result: dict[str, Any] = {
        **diagnostic_url_payload(response_url),
        "status": status,
        "content_type": _normalized_content_type(headers.get("content-type")) or None,
        "content_length_bytes": _content_length_diagnostic(headers),
        "transfer_encoding_present": bool(
            normalize_text(headers.get("transfer-encoding"))
        ),
        "chunked_transfer_declared": (
            "chunked" in normalize_text(headers.get("transfer-encoding")).lower()
        ),
        "captured_html_bytes": captured_html_bytes,
        "navigation_timing": _main_document_navigation_diagnostic(page),
    }
    request = _diagnostic_event_attr(response, "request")
    tracked = document_requests.get(id(request)) if request is not None else None
    if tracked is not None:
        lifecycle, started_at = tracked
        result["request_lifecycle"] = {
            key: lifecycle[key]
            for key in (
                "response_received_observed",
                "response_received_ms",
                "request_finished_observed",
                "request_finished_ms",
                "request_failed_observed",
                "request_failed_ms",
                "request_failure",
            )
            if key in lifecycle
        }
        result["request_lifecycle"]["observed_ms"] = round(
            max(0.0, time.monotonic() - started_at) * 1000,
            3,
        )
    return result


def _content_length_diagnostic(headers: Mapping[str, str]) -> int | None:
    raw_value = normalize_text(headers.get("content-length"))
    if not raw_value.isascii() or not raw_value.isdecimal():
        return None
    value = int(raw_value)
    return value if value >= 0 else None


def _finite_nonnegative_diagnostic_number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if numeric < 0 or numeric == float("inf") or numeric != numeric:
        return None
    if numeric.is_integer():
        return int(numeric)
    return round(numeric, 3)


def _main_document_navigation_diagnostic(page: Any) -> dict[str, Any]:
    try:
        raw = page.evaluate(_MAIN_DOCUMENT_NAVIGATION_DIAGNOSTIC_SCRIPT)
    except Exception as exc:
        return {
            "available": False,
            "error_type": type(exc).__name__,
        }
    if not isinstance(raw, Mapping):
        return {"available": False}
    ready_state = normalize_text(str(raw.get("documentReadyState") or "")).lower()
    if ready_state not in {"loading", "interactive", "complete"}:
        ready_state = ""
    result: dict[str, Any] = {
        "available": True,
        "document_ready_state": ready_state or None,
    }
    navigation = raw.get("navigation")
    if not isinstance(navigation, Mapping):
        result["navigation_entry_present"] = False
        return result
    result["navigation_entry_present"] = True
    for source_key, target_key in (
        ("responseStart", "response_start_ms"),
        ("responseEnd", "response_end_ms"),
        ("domInteractive", "dom_interactive_ms"),
        ("domContentLoadedEventEnd", "dom_content_loaded_event_end_ms"),
        ("loadEventEnd", "load_event_end_ms"),
        ("duration", "duration_ms"),
        ("transferSize", "transfer_size_bytes"),
        ("encodedBodySize", "encoded_body_size_bytes"),
        ("decodedBodySize", "decoded_body_size_bytes"),
    ):
        result[target_key] = _finite_nonnegative_diagnostic_number(
            navigation.get(source_key)
        )
    navigation_type = normalize_text(str(navigation.get("type") or "")).lower()
    result["navigation_type"] = (
        navigation_type
        if navigation_type in {"navigate", "reload", "back_forward", "prerender"}
        else None
    )
    next_hop_protocol = normalize_text(str(navigation.get("nextHopProtocol") or ""))
    result["next_hop_protocol"] = next_hop_protocol[:32] if next_hop_protocol else None
    response_end = result.get("response_end_ms")
    dom_content_loaded_end = result.get("dom_content_loaded_event_end_ms")
    load_event_end = result.get("load_event_end_ms")
    result["response_completed"] = bool(
        isinstance(response_end, (int, float)) and response_end > 0
    )
    result["dom_content_loaded_completed"] = bool(
        isinstance(dom_content_loaded_end, (int, float)) and dom_content_loaded_end > 0
    )
    result["load_event_completed"] = bool(
        isinstance(load_event_end, (int, float)) and load_event_end > 0
    )
    return result


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


def _encoded_browser_image_payload(
    body: bytes | bytearray,
    *,
    content_type: str,
    final_url: str,
    status: int,
    width: int,
    height: int,
) -> BrowserImagePayload | None:
    if not body:
        return None
    return {
        "bodyB64": base64.b64encode(bytes(body)).decode("ascii"),
        "contentType": content_type or "image/png",
        "url": final_url,
        "status": status,
        "width": width,
        "height": height,
    }


def _mapped_browser_image_payload(
    value: Any,
    *,
    fallback_content_type: str,
    fallback_url: str,
    fallback_status: int,
    width: int,
    height: int,
) -> BrowserImagePayload | None:
    if not isinstance(value, Mapping) or value.get("ok") is False:
        return None
    encoded = normalize_text(str(value.get("bodyB64") or ""))
    if not encoded:
        data_url = normalize_text(str(value.get("dataURL") or ""))
        if "," in data_url:
            encoded = data_url.split(",", 1)[1]
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except Exception:
        return None
    if not decoded:
        return None
    return {
        "bodyB64": encoded,
        "contentType": _normalized_content_type(
            str(value.get("contentType") or fallback_content_type)
        )
        or "image/png",
        "url": normalize_text(str(value.get("url") or "")) or fallback_url,
        "status": _safe_int(value.get("status"), default=fallback_status),
        "width": max(0, _safe_int(value.get("width"), default=width)),
        "height": max(0, _safe_int(value.get("height"), default=height)),
    }


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
        if response_is_image and response is not None:
            try:
                response_body = response.body()
            except Exception:
                response_body = b""
            if isinstance(response_body, (bytes, bytearray)):
                payload = _encoded_browser_image_payload(
                    response_body,
                    content_type=content_type,
                    final_url=normalized_final_url,
                    status=status,
                    width=width,
                    height=height,
                )
                if payload is not None:
                    return payload

        try:
            array_buffer_result = page.evaluate(
                _IMAGE_ARRAY_BUFFER_EXPORT_SCRIPT,
                [normalized_final_url],
            )
        except Exception:
            array_buffer_result = None
        payload = _mapped_browser_image_payload(
            array_buffer_result,
            fallback_content_type=content_type,
            fallback_url=normalized_final_url,
            fallback_status=status if response_is_image else 200,
            width=width,
            height=height,
        )
        if payload is not None:
            return payload

        if discovered_loaded_image or image_element is not None:
            try:
                canvas_result = page.evaluate(
                    _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
                    [normalized_final_url, 1, 1],
                )
            except Exception:
                canvas_result = None
            payload = _mapped_browser_image_payload(
                canvas_result,
                fallback_content_type="image/png",
                fallback_url=normalized_final_url,
                fallback_status=200,
                width=width,
                height=height,
            )
            if payload is not None:
                return payload

    html = ""
    try:
        html = str(page.content() or "")
    except Exception:
        html = ""

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


def _storage_state_path(config: PlaywrightRuntimeConfig) -> Path | None:
    return _runtime_paths().storage_state_path(config)


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
        if runtime_context is not None:
            runtime_context.raise_if_cancelled()
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
        candidate_trace["dom_readiness_fingerprint_present"] = bool(
            normalize_text(str(getattr(body_readiness, "fingerprint", "") or ""))
        )
        candidate_trace["dom_readiness_result"] = (
            "ready"
            if body_readiness.ready
            else ("timeout" if body_readiness.attempted else "unsupported")
        )
    elif normalized_selector and wait_seconds > 0:
        if runtime_context is not None:
            runtime_context.raise_if_cancelled()
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
        if runtime_context is not None:
            runtime_context.raise_if_cancelled()
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
        if runtime_context is not None:
            runtime_context.raise_if_cancelled()
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
        details.update({"challenge_provider": "aws_waf"})
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
        return manager, browser_context, page
    except PlaywrightBrowserFailure:
        if not reused:
            _safe_close(browser_context)
            _safe_close(manager)
        raise
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
        # Unknown names are retained for deterministic browser doubles.
        route_timeout_ms = configured_timeout_ms
    return min(configured_timeout_ms, route_timeout_ms)


def _browser_html_deadline(
    *,
    started_at: float,
    timeout_ms: int,
    runtime_context: RuntimeContext | None,
) -> float:
    deadline = started_at + (timeout_ms / 1000.0)
    if runtime_context is not None and runtime_context.deadline_monotonic is not None:
        return min(deadline, runtime_context.deadline_monotonic)
    return deadline


def _record_browser_challenge_signal(
    trace: dict[str, Any],
    *,
    reason: str,
    status: int | None,
    final_url: str,
) -> None:
    challenge_signals = trace.setdefault("challenge_signals", [])
    if not isinstance(challenge_signals, list):
        return
    _append_bounded_event(
        challenge_signals,
        {
            "reason": normalize_text(reason).lower(),
            "status": status,
            **diagnostic_url_payload(final_url),
        },
    )


def _wiley_document_doi_evidence(html_text: str) -> list[tuple[str, str]]:
    """Return normalized DOI evidence from Wiley-owned identity nodes."""

    try:
        soup = BeautifulSoup(html_text, choose_parser())
    except Exception:
        return []

    evidence: list[tuple[str, str]] = []

    def add(source: str, value: Any, *, from_url: bool = False) -> None:
        raw_value = normalize_text(str(value or ""))
        if not raw_value:
            return
        doi = extract_doi_from_url(raw_value) if from_url else extract_doi(raw_value)
        normalized = normalize_doi(doi or "")
        item = (source, normalized)
        if normalized and item not in evidence:
            evidence.append(item)

    for node in soup.find_all("meta"):
        attrs = getattr(node, "attrs", None) or {}
        name = normalize_text(
            str(attrs.get("name") or attrs.get("property") or "")
        ).lower()
        if name in _WILEY_DOI_META_NAMES:
            add("citation_meta", attrs.get("content"))

    for node in soup.select("link[rel~='canonical']"):
        attrs = getattr(node, "attrs", None) or {}
        add("canonical", attrs.get("href"), from_url=True)

    for node in soup.select(".epub-doi"):
        add("epub_doi", node.get_text(" ", strip=True))
        attrs = getattr(node, "attrs", None) or {}
        add("epub_doi", attrs.get("href"), from_url=True)
        for link in node.select("a[href]"):
            add(
                "epub_doi",
                (getattr(link, "attrs", None) or {}).get("href"),
                from_url=True,
            )
    return evidence


def _wiley_http_access_status_review(
    *,
    publisher: str,
    return_image_payload: bool,
    status: int | None,
    requested_doi: str,
    requested_url: str,
    final_url: str,
    html_text: str,
    title: str,
    body_ready: bool,
) -> dict[str, Any] | None:
    if (
        normalize_text(publisher).lower() != "wiley"
        or status not in _WILEY_REVIEWABLE_HTTP_STATUSES
        or return_image_payload
    ):
        return None

    expected_doi = normalize_doi(requested_doi)
    doi_evidence = _wiley_document_doi_evidence(html_text)
    matching_sources = [
        source for source, observed_doi in doi_evidence if observed_doi == expected_doi
    ]
    evidence_sources = list(dict.fromkeys(source for source, _doi in doi_evidence))

    preliminary = HtmlQualityAssessor("wiley").assess(
        "",
        {"doi": expected_doi},
        html_text=html_text,
        structure_html_text=html_text,
        title=title or None,
        response_status=None,
        requested_url=requested_url,
        final_url=final_url,
    )
    blocking_signals = list(
        dict.fromkeys(
            [
                *preliminary.hard_negative_signals,
                *preliminary.blocking_fallback_signals,
            ]
        )
    )
    doi_match = bool(expected_doi and matching_sources)
    candidate_confirmed = bool(body_ready and doi_match and not blocking_signals)
    if not body_ready:
        reason = "body_not_ready"
    elif not expected_doi:
        reason = "requested_doi_missing"
    elif not doi_evidence:
        reason = "doi_evidence_missing"
    elif not doi_match:
        reason = "doi_mismatch"
    elif blocking_signals:
        reason = "blocking_signal"
    else:
        reason = "pending_fulltext_acceptance"

    return {
        "status": status,
        "body_ready": bool(body_ready),
        "doi_evidence_present": bool(doi_evidence),
        "doi_evidence_sources": evidence_sources,
        "doi_match": doi_match,
        "doi_match_sources": list(dict.fromkeys(matching_sources)),
        "blocking_signals": blocking_signals,
        "candidate_confirmed": candidate_confirmed,
        "status_override_applied": False,
        "fulltext_acceptance": "pending" if candidate_confirmed else "not_attempted",
        "accepted": False,
        "reason": reason,
    }


def _reject_wiley_http_access_status_review(
    review: dict[str, Any] | None,
    *,
    blocking_reason: str,
) -> None:
    if review is None or review.get("candidate_confirmed") is not True:
        return
    signals = list(review.get("blocking_signals") or [])
    normalized_reason = normalize_text(blocking_reason).lower()
    if normalized_reason and normalized_reason not in signals:
        signals.append(normalized_reason)
    review.update(
        {
            "blocking_signals": signals,
            "candidate_confirmed": False,
            "status_override_applied": False,
            "fulltext_acceptance": "not_attempted",
            "accepted": False,
            "reason": "blocking_signal",
        }
    )


def _record_wiley_http_access_status_review(
    candidate_trace: dict[str, Any],
    review: dict[str, Any] | None,
    *,
    apply_override: bool = False,
) -> bool:
    if review is None:
        return False
    confirmed = review.get("candidate_confirmed") is True
    if apply_override:
        review["status_override_applied"] = confirmed
    candidate_trace[_HTTP_ACCESS_STATUS_REVIEW_KEY] = review
    return confirmed


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
    backend_name = "camoufox"
    active_blocked_resource_types = _active_browser_resource_types(
        backend_name=backend_name,
        disable_media=disable_media,
        options=options,
    )
    empty_script_response_urls = frozenset(
        str(item).strip()
        for item in options.empty_script_response_urls
        if str(item).strip()
    )
    readiness_budget_seconds = options.readiness_budget_seconds
    reuse_runtime_page = options.reuse_runtime_page
    pnas_metrics_request = None
    if normalize_text(publisher).lower() == "pnas":
        from .pnas import _is_sidebar_metrics_url

        pnas_metrics_request = _is_sidebar_metrics_url

    last_failure: PlaywrightBrowserFailure | None = None
    latest_browser_context_seed: Mapping[str, Any] | None = None
    caller_timeout_ms = (
        config.timeout_ms if max_timeout_ms is None else max(1, max_timeout_ms)
    )
    timeout_ms = _browser_route_timeout_ms(
        publisher,
        configured_timeout_ms=caller_timeout_ms,
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
        "empty_script_response_count": 0,
        "return_image_payload": bool(return_image_payload),
        "return_screenshot": bool(return_screenshot),
        "lightweight_seed_only": bool(lightweight_seed_only),
        "article_body_wait_enabled": bool(readiness.wait_for_article_body),
        "selector_wait_enabled": bool(normalized_wait_for_selector),
        "wait_for_selector": normalized_wait_for_selector or None,
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
    local_deadline = _browser_html_deadline(
        started_at=overall_started,
        timeout_ms=timeout_ms,
        runtime_context=runtime_context,
    )
    trace["timeout_budget_ms"] = timeout_ms
    readiness_deadline: float | None = None
    observed_blocked_resource_types: set[str] = set()

    def remaining_timeout_ms() -> int:
        remaining = max(0.0, local_deadline - time.monotonic())
        if remaining <= 0:
            return 0
        return max(1, min(timeout_ms, int(remaining * 1000)))

    manager = None
    browser_context = None
    page = None
    page_diagnostic_listeners: list[tuple[str, Callable[[Any], None]]] = []
    document_request_diagnostics: dict[int, tuple[dict[str, Any], float]] = {}
    shared_page_session = _runtime_figure_page_session(
        runtime_context,
        create=bool(reuse_runtime_page),
    )

    try:
        if runtime_context is not None:
            runtime_context.raise_if_cancelled()
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
        (
            page_diagnostic_listeners,
            document_request_diagnostics,
        ) = _install_page_diagnostic_listeners(page, trace)

        # Science can replace an initial denied document through an automatic
        # main-frame navigation while readiness waits. Keep response ownership
        # separate from the bounded, serializable diagnostic event summaries.
        science_document_requests: dict[int, Any] = {}
        science_document_responses: list[Any] = []
        science_finished_requests: set[int] = set()
        if normalize_text(publisher).lower() == "science":

            def science_request_started(request: Any) -> None:
                if (
                    _diagnostic_event_value(
                        getattr(request, "is_navigation_request", False)
                    )
                    and _diagnostic_event_attr(request, "resource_type") == "document"
                    and getattr(page, "main_frame", None) is not None
                    and _diagnostic_event_attr(request, "frame")
                    is getattr(page, "main_frame", None)
                ):
                    science_document_requests[id(request)] = request

            def science_response_received(response: Any) -> None:
                if (
                    id(_diagnostic_event_attr(response, "request"))
                    in science_document_requests
                ):
                    science_document_responses.append(response)

            def science_request_finished(request: Any) -> None:
                if id(request) in science_document_requests:
                    science_finished_requests.add(id(request))

            for event, callback in (
                ("request", science_request_started),
                ("response", science_response_received),
                ("requestfinished", science_request_finished),
            ):
                if callable(getattr(page, "on", None)):
                    page.on(event, callback)
                    page_diagnostic_listeners.append((event, callback))

        def route_handler(route: Any) -> None:
            try:
                resource_type = normalize_text(
                    str(route.request.resource_type or "")
                ).lower()
                request_url = str(route.request.url or "")
                if (
                    resource_type == "script"
                    and request_url in empty_script_response_urls
                ):
                    try:
                        route.fulfill(
                            status=200,
                            content_type="application/javascript",
                            body="",
                        )
                    except Exception:
                        with contextlib.suppress(Exception):
                            route.continue_()
                    else:
                        trace["empty_script_response_count"] = (
                            int(trace.get("empty_script_response_count") or 0) + 1
                        )
                    return
                sidebar_metrics = bool(
                    pnas_metrics_request and pnas_metrics_request(request_url)
                )
                if resource_type in active_blocked_resource_types or sidebar_metrics:
                    trace["blocked_request_count"] = (
                        int(trace.get("blocked_request_count") or 0) + 1
                    )
                    observed_blocked_resource_types.add(resource_type)
                    trace["blocked_request_types"] = sorted(
                        observed_blocked_resource_types
                    )
                    if sidebar_metrics:
                        trace["blocked_sidebar_metrics_count"] = (
                            int(trace.get("blocked_sidebar_metrics_count") or 0) + 1
                        )
                    route.abort()
                    return
                route.continue_()
            except Exception:
                with contextlib.suppress(Exception):
                    route.continue_()

        if (
            active_blocked_resource_types
            or empty_script_response_urls
            or pnas_metrics_request
        ):
            with contextlib.suppress(Exception):
                page.route("**/*", route_handler)

        for url in candidate_urls:
            if runtime_context is not None:
                runtime_context.raise_if_cancelled()
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
            science_document_requests.clear()
            science_document_responses.clear()
            science_finished_requests.clear()
            try:
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
                    candidate_trace["main_document_response"] = (
                        _main_document_response_diagnostic(
                            response,
                            page=page,
                            fallback_url=final_url,
                            status=status,
                            headers=headers,
                            document_requests=document_request_diagnostics,
                            captured_html_bytes=len(html.encode("utf-8")),
                        )
                    )
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
                html = str(page.content() or "")
                title = normalize_text(str(page.title() or ""))
                if not title and normalize_text(publisher).lower() != "ieee":
                    title = (
                        extract_page_title(BeautifulSoup(html, choose_parser())) or ""
                    )
                if science_document_responses:
                    current_response = science_document_responses[-1]
                    current_url = normalize_text(
                        str(_diagnostic_event_attr(current_response, "url") or "")
                    )
                    target_doi = normalize_doi(config.doi)
                    if (
                        id(_diagnostic_event_attr(current_response, "request"))
                        in science_finished_requests
                        and id(_diagnostic_event_attr(current_response, "request"))
                        == next(reversed(science_document_requests))
                        and urllib.parse.urldefrag(current_url)[0]
                        == urllib.parse.urldefrag(final_url)[0]
                        and urllib.parse.urlsplit(current_url).hostname
                        in {"science.org", "www.science.org"}
                        and target_doi
                        and normalize_doi(extract_doi_from_url(current_url))
                        == target_doi
                    ):
                        response = current_response
                status = _browser_response_status(response, zero_as_none=False)
                headers = _browser_response_headers(response)
                candidate_trace["status"] = status
                candidate_trace["main_document_response"] = (
                    _main_document_response_diagnostic(
                        response,
                        page=page,
                        fallback_url=final_url,
                        status=status,
                        headers=headers,
                        document_requests=document_request_diagnostics,
                        captured_html_bytes=len(html.encode("utf-8")),
                    )
                )
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
                    _bounded_diagnostic_text(exc) or exc.__class__.__name__
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
            # labels. Wiley may provisionally review 401/403 below; challenges
            # and every unconfirmed HTTP failure still fail closed.
            substantive_body_ready = bool(
                readiness.wait_for_article_body
                and candidate_trace.get("dom_readiness_ready")
            )
            stable_wiley_body_ready = bool(
                substantive_body_ready
                and candidate_trace.get("dom_readiness_fingerprint_present")
            )
            http_access_status_review = _wiley_http_access_status_review(
                publisher=publisher,
                return_image_payload=return_image_payload,
                status=status,
                requested_doi=config.doi,
                requested_url=normalized_url,
                final_url=final_url,
                html_text=html,
                title=title or "",
                body_ready=stable_wiley_body_ready,
            )
            wiley_candidate_confirmed = _record_wiley_http_access_status_review(
                candidate_trace,
                http_access_status_review,
            )
            status_for_block_detection = None if wiley_candidate_confirmed else status
            detected = detect_html_block(
                title or "",
                summary,
                status_for_block_detection,
                substantive_body_ready=substantive_body_ready,
                html_text="" if required_selector_ready else html,
                response_headers={} if required_selector_ready else headers,
            )
            if detected is not None and not return_image_payload:
                _reject_wiley_http_access_status_review(
                    http_access_status_review,
                    blocking_reason=detected.reason,
                )
                _record_browser_challenge_signal(
                    trace,
                    reason=detected.reason,
                    status=status,
                    final_url=final_url,
                )
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
                                backend="camoufox",
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
            _record_wiley_http_access_status_review(
                candidate_trace,
                http_access_status_review,
                apply_override=True,
            )
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
                                backend="camoufox",
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
        _remove_page_diagnostic_listeners(page, page_diagnostic_listeners)
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
