"""DOM readiness probes after browser HTML navigation."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ...utils import normalize_text
from ..browser_workflow.fetchers.readiness import (
    BodyDomReadinessResult,
    wait_for_atypon_body_dom_ready,
)
from .types import BrowserHtmlReadiness

if TYPE_CHECKING:
    from ...runtime import RuntimeContext

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


def _wait_for_article_body_readiness(
    page: Any,
    *,
    publisher: str,
    wait_seconds: int,
    timeout_ms: int,
    request_started: float,
    runtime_context: RuntimeContext | None,
    candidate_trace: dict[str, Any],
    readiness_timeout_seconds: float | None,
) -> BodyDomReadinessResult:
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
    readiness_kwargs: dict[str, Any] = {}
    if runtime_context is not None:
        readiness_kwargs["cancel_check"] = runtime_context.raise_if_cancelled
    body_readiness = wait_for_atypon_body_dom_ready(
        page,
        publisher,
        timeout_seconds=max(0.0, body_timeout_seconds),
        **readiness_kwargs,
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
    blocking_reason = getattr(body_readiness, "blocking_reason", None)
    candidate_trace["dom_readiness_result"] = (
        "ready"
        if body_readiness.ready
        else (
            "blocked"
            if blocking_reason
            else "timeout"
            if body_readiness.attempted
            else "unsupported"
        )
    )
    if blocking_reason:
        candidate_trace["dom_readiness_blocking_reason"] = blocking_reason
    return body_readiness


def _wait_for_selector_readiness(
    page: Any,
    *,
    normalized_selector: str,
    selector_text: str,
    require_selector: bool,
    wait_seconds: int,
    timeout_ms: int,
    request_started: float,
    runtime_context: RuntimeContext | None,
    candidate_trace: dict[str, Any],
    readiness_timeout_seconds: float | None,
) -> None:
    if runtime_context is not None:
        runtime_context.raise_if_cancelled()
    remaining_timeout_ms = max(
        1,
        int(
            ((float(timeout_ms) / 1000.0) - (time.monotonic() - request_started)) * 1000
        ),
    )
    selector_budget_ms = (
        max(1, int(readiness_timeout_seconds * 1000))
        if readiness_timeout_seconds is not None
        else max(1, int(wait_seconds) * 1000)
    )
    selector_timeout_ms = min(selector_budget_ms, remaining_timeout_ms)
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
    candidate_trace["selector_readiness_required"] = bool(require_selector)
    candidate_trace["selector_readiness_expected_text"] = selector_text or None
    candidate_trace["selector_readiness_seconds"] = round(
        time.monotonic() - selector_started,
        3,
    )
    candidate_trace["dom_readiness_result"] = (
        "ready" if candidate_trace.get("selector_readiness_ready") else "timeout"
    )


def _wait_for_fixed_delay(
    page: Any,
    *,
    wait_seconds: int,
    timeout_ms: int,
    request_started: float,
    runtime_context: RuntimeContext | None,
    candidate_trace: dict[str, Any],
    readiness_timeout_seconds: float | None,
) -> None:
    if runtime_context is not None:
        runtime_context.raise_if_cancelled()
    remaining_wait_ms = max(
        0,
        int(
            ((float(timeout_ms) / 1000.0) - (time.monotonic() - request_started)) * 1000
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


def wait_for_browser_html_readiness(
    page: Any,
    *,
    publisher: str,
    readiness: BrowserHtmlReadiness,
    wait_seconds: int,
    timeout_ms: int,
    request_started: float,
    runtime_context: RuntimeContext | None,
    candidate_trace: dict[str, Any],
    readiness_timeout_seconds: float | None = None,
) -> BodyDomReadinessResult | None:
    readiness_operation_started = time.monotonic()
    normalized_selector = normalize_text(readiness.selector)
    selector_text = normalize_text(readiness.selector_text)
    body_readiness: BodyDomReadinessResult | None = None
    selector_wait_attempted = False

    if readiness.wait_for_article_body:
        body_readiness = _wait_for_article_body_readiness(
            page,
            publisher=publisher,
            wait_seconds=wait_seconds,
            timeout_ms=timeout_ms,
            request_started=request_started,
            runtime_context=runtime_context,
            candidate_trace=candidate_trace,
            readiness_timeout_seconds=readiness_timeout_seconds,
        )
    elif normalized_selector and wait_seconds > 0:
        selector_wait_attempted = True
        _wait_for_selector_readiness(
            page,
            normalized_selector=normalized_selector,
            selector_text=selector_text,
            require_selector=readiness.require_selector,
            wait_seconds=wait_seconds,
            timeout_ms=timeout_ms,
            request_started=request_started,
            runtime_context=runtime_context,
            candidate_trace=candidate_trace,
            readiness_timeout_seconds=readiness_timeout_seconds,
        )

    if (
        (body_readiness is None or not body_readiness.attempted)
        and not selector_wait_attempted
        and wait_seconds > 0
    ):
        _wait_for_fixed_delay(
            page,
            wait_seconds=wait_seconds,
            timeout_ms=timeout_ms,
            request_started=request_started,
            runtime_context=runtime_context,
            candidate_trace=candidate_trace,
            readiness_timeout_seconds=readiness_timeout_seconds,
        )
    if wait_seconds > 0:
        readiness_elapsed = max(
            0.0,
            time.monotonic() - readiness_operation_started,
        )
        candidate_trace["dom_readiness_seconds"] = round(readiness_elapsed, 3)
    return body_readiness
