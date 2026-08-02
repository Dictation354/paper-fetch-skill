"""DOM readiness checks for provider browser-workflow HTML fetchers."""

from __future__ import annotations

from dataclasses import dataclass, replace
import time
from typing import Any
from collections.abc import Mapping

from ....provider_catalog import provider_body_text_thresholds
from ....utils import normalize_text
import contextlib

ATYPON_BODY_READY_SELECTORS: Mapping[str, tuple[str, ...]] = {
    "annualreviews": (
        "#itemFullTextId",
        "#html_fulltext",
        ".articleSection",
    ),
    "wiley": (
        ".article-section__content.en.main",
        "section.article-section__content",
        ".article-section__content",
    ),
    "science": (
        "[data-extent='bodymatter']",
        "[property='articleBody']",
        "#bodymatter",
        ".article__fulltext",
        ".article-view",
    ),
    "pnas": (
        ".article__fulltext",
        ".article-content",
        ".core-container",
    ),
    "ams": (
        "#articleBody",
        "#bodymatter",
        ".articleFullText",
        ".NLM_body",
        ".component-content-html",
        ".article__fulltext",
    ),
    "acs": (
        ".article-body",
        ".widget-ArticleFulltext",
    ),
    "iop": (
        "[itemprop='articleBody']",
        "[property='articleBody']",
        ".article-content",
        ".article-body",
        ".article-full-text",
        ".article-text",
    ),
    "aip": (
        ".article-body .widget-ArticleFulltext",
        ".widget-ArticleFulltext",
        ".article-body",
    ),
}

_BODY_READY_POLL_INTERVAL_MS = 750
_BODY_READY_SCRIPT = """
({ selectors, minChars }) => {
  const normalize = (value) => (value || "").replace(/\\s+/g, " ").trim();
  let best = null;
  for (const selector of selectors || []) {
    let nodes = [];
    try {
      nodes = Array.from(document.querySelectorAll(selector));
    } catch (error) {
      continue;
    }
    for (const node of nodes) {
      const text = normalize(node.innerText || node.textContent || "");
      const textLength = text.length;
      const paragraphCount = node.querySelectorAll("p").length;
      const headingCount = node.querySelectorAll("h1,h2,h3,h4,h5,h6,[role='heading']").length;
      const ready = textLength >= minChars && (paragraphCount >= 2 || headingCount >= 1);
      const fingerprint = [
        selector,
        textLength,
        paragraphCount,
        headingCount,
        text.slice(0, 160),
        text.slice(-160),
      ].join("|");
      const candidate = {
        ready,
        selector,
        textLength,
        paragraphCount,
        headingCount,
        fingerprint,
      };
      if (ready) {
        return candidate;
      }
      if (best === null || textLength > best.textLength) {
        best = candidate;
      }
    }
  }
  return best || {
    ready: false,
    selector: null,
    textLength: 0,
    paragraphCount: 0,
    headingCount: 0,
    fingerprint: "",
  };
}
"""


@dataclass(frozen=True)
class BodyDomReadinessResult:
    attempted: bool
    ready: bool
    provider: str
    selector: str | None = None
    text_length: int = 0
    paragraph_count: int = 0
    heading_count: int = 0
    fingerprint: str = ""
    elapsed_ms: int = 0


def atypon_body_ready_selectors(provider: str | None) -> tuple[str, ...]:
    return ATYPON_BODY_READY_SELECTORS.get(normalize_text(provider).lower(), ())


def _coerce_readiness_payload(
    payload: Any,
    *,
    provider: str,
    elapsed_ms: int,
) -> BodyDomReadinessResult:
    if not isinstance(payload, Mapping):
        return BodyDomReadinessResult(
            attempted=True,
            ready=False,
            provider=provider,
            elapsed_ms=elapsed_ms,
        )

    def safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    return BodyDomReadinessResult(
        attempted=True,
        ready=bool(payload.get("ready")),
        provider=provider,
        selector=normalize_text(str(payload.get("selector") or "")) or None,
        text_length=max(0, safe_int(payload.get("textLength"))),
        paragraph_count=max(0, safe_int(payload.get("paragraphCount"))),
        heading_count=max(0, safe_int(payload.get("headingCount"))),
        fingerprint=normalize_text(str(payload.get("fingerprint") or "")),
        elapsed_ms=elapsed_ms,
    )


def wait_for_atypon_body_dom_ready(
    page: Any,
    provider: str | None,
    *,
    timeout_seconds: float,
    poll_interval_ms: int = _BODY_READY_POLL_INTERVAL_MS,
) -> BodyDomReadinessResult:
    normalized_provider = normalize_text(provider).lower()
    selectors = atypon_body_ready_selectors(normalized_provider)
    evaluate = getattr(page, "evaluate", None)
    if not selectors or not callable(evaluate):
        return BodyDomReadinessResult(
            attempted=False,
            ready=False,
            provider=normalized_provider,
        )

    min_chars = provider_body_text_thresholds(normalized_provider).short_body_min_chars
    timeout_budget_seconds = max(0.0, float(timeout_seconds or 0))
    interval_ms = max(1, int(poll_interval_ms))
    started_at = time.monotonic()
    operation_deadline = started_at + timeout_budget_seconds
    previous_ready_fingerprint = ""
    last_result = BodyDomReadinessResult(
        attempted=True,
        ready=False,
        provider=normalized_provider,
    )

    while True:
        try:
            payload = evaluate(
                _BODY_READY_SCRIPT,
                {"selectors": list(selectors), "minChars": min_chars},
            )
        except Exception:
            payload = None
        elapsed_ms = max(0, int((time.monotonic() - started_at) * 1000))
        current = _coerce_readiness_payload(
            payload,
            provider=normalized_provider,
            elapsed_ms=elapsed_ms,
        )
        last_result = current
        if current.ready and current.fingerprint:
            if current.fingerprint == previous_ready_fingerprint:
                return current
            previous_ready_fingerprint = current.fingerprint
        else:
            previous_ready_fingerprint = ""

        remaining_seconds = operation_deadline - time.monotonic()
        if remaining_seconds <= 0:
            if last_result.ready:
                return replace(
                    last_result,
                    ready=False,
                    elapsed_ms=max(
                        last_result.elapsed_ms,
                        int((time.monotonic() - started_at) * 1000),
                    ),
                )
            return replace(
                last_result,
                elapsed_ms=max(
                    last_result.elapsed_ms,
                    int((time.monotonic() - started_at) * 1000),
                ),
            )

        wait_ms = min(interval_ms, max(1, int(remaining_seconds * 1000)))
        wait_for_timeout = getattr(page, "wait_for_timeout", None)
        if callable(wait_for_timeout):
            with contextlib.suppress(Exception):
                wait_for_timeout(wait_ms)


__all__ = [
    "ATYPON_BODY_READY_SELECTORS",
    "BodyDomReadinessResult",
    "atypon_body_ready_selectors",
    "wait_for_atypon_body_dom_ready",
]
