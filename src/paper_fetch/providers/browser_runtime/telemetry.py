"""Browser page event telemetry, navigation timing, and user-agent inspection."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Mapping
from typing import Any

from ...http import diagnostic_url_payload, redact_text_for_diagnostics
from ...utils import normalize_text
from ..browser_workflow.fetchers.context import (
    _browser_response_headers,
    _browser_response_status,
)

MAX_BROWSER_DIAGNOSTIC_EVENTS = 8
MAX_BROWSER_DIAGNOSTIC_TEXT_CHARS = 500
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


def browser_page_user_agent(page: Any) -> str | None:
    try:
        user_agent = page.evaluate("() => navigator.userAgent")
    except Exception:
        return None
    normalized = str(user_agent or "").strip()
    return normalized or None


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


def _normalized_content_type(value: str | None) -> str:
    return normalize_text(str(value or "")).split(";", 1)[0].lower()


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


def _record_candidate_document_diagnostics(
    candidate_trace: dict[str, Any],
    *,
    response: Any,
    page: Any,
    final_url: str,
    status: int | None,
    headers: Mapping[str, Any],
    document_requests: Mapping[int, tuple[Mapping[str, Any], float]],
    html: str,
) -> None:
    candidate_trace["status"] = status
    final = diagnostic_url_payload(final_url)
    candidate_trace["final_url"] = final.get("url")
    candidate_trace["final_url_sha256"] = final.get("url_sha256")
    candidate_trace["main_document_response"] = _main_document_response_diagnostic(
        response,
        page=page,
        fallback_url=final_url,
        status=status,
        headers=headers,
        document_requests=document_requests,
        captured_html_bytes=len(html.encode("utf-8")),
    )


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
