"""Shared browser-workflow runtime helpers for Wiley/Science/PNAS."""

from __future__ import annotations

import base64
import html as html_lib
import logging
import re
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Mapping

from ..config import build_user_agent
from ..extraction.html import decode_html
from ..extraction.image_payloads import image_mime_type_from_bytes
from ..extraction.html.signals import SciencePnasHtmlFailure
from ..logging_utils import emit_structured_log
from ..metadata_types import ProviderMetadata
from ..models import AssetProfile, article_from_markdown, coerce_asset_failure_diagnostics, metadata_only_article
from ..publisher_identity import normalize_doi
from ..tracing import merge_trace, source_trail_from_trace, trace_from_markers
from ..utils import dedupe_authors, empty_asset_results, extend_unique, normalize_text
from ._flaresolverr import (
    FetchedPublisherHtml,
    FlareSolverrFailure,
    ensure_runtime_ready,
    fetch_html_with_flaresolverr,
    load_runtime_config,
    merge_browser_context_seeds,
    probe_runtime_status,
    warm_browser_context_with_flaresolverr,
)
from ._pdf_fallback import PdfFallbackFailure, fetch_pdf_with_playwright
from ._science_pnas_html import (
    extract_browser_workflow_asset_html_scopes,
    extract_science_pnas_markdown,
    rewrite_inline_figure_links,
)
from ._browser_workflow_shared import (
    build_browser_workflow_html_candidates,
    build_browser_workflow_pdf_candidates,
    extract_pdf_url_from_crossref,
    preferred_html_candidate_from_landing_page as _preferred_html_candidate_from_landing_page,
)
from ._waterfall import ProviderWaterfallStep, run_provider_waterfall
from .base import PreparedFetchResultPayload, ProviderArtifacts, ProviderClient, ProviderContent, ProviderFailure, RawFulltextPayload
from .html_assets import (
    download_supplementary_assets,
    download_figure_assets_with_image_document_fetcher,
    extract_full_size_figure_image_url,
    extract_scoped_html_assets,
    html_asset_identity_key,
    looks_like_full_size_asset_url,
    split_body_and_supplementary_assets,
    supplementary_response_block_reason,
)

logger = logging.getLogger("paper_fetch.providers.browser_workflow")

_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS = 15000
_CLOUDFLARE_CHALLENGE_TITLE_TOKENS = (
    "just a moment",
    "attention required",
    "checking your browser",
)
_LOADED_IMAGE_CANVAS_EXPORT_SCRIPT = """
([targetUrl, minWidth, minHeight]) => {
  const bytesToBase64 = (bytes) => {
    let binary = '';
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
      const chunk = bytes.subarray(index, index + chunkSize);
      binary += String.fromCharCode(...chunk);
    }
    return btoa(binary);
  };
  const normalizeUrl = (value) => {
    try {
      return new URL(String(value || ''), document.baseURI).href;
    } catch (error) {
      return String(value || '');
    }
  };
  const classifyCanvasError = (error) => {
    const name = String((error && error.name) || '');
    const message = String((error && error.message) || error || '');
    const blob = `${name} ${message}`.toLowerCase();
    if (
      name === 'SecurityError'
      || blob.includes('tainted')
      || blob.includes('cross-origin')
      || blob.includes('insecure operation')
    ) {
      return {
        reason: 'canvas_tainted',
        error: name || message,
      };
    }
    return {
      reason: 'canvas_serialization_failed',
      error: name || message,
    };
  };
  const normalizedTarget = normalizeUrl(targetUrl);
  const loadedImages = Array.from(document.images || []).filter((image) =>
    image.complete
    && image.naturalWidth >= minWidth
    && image.naturalHeight >= minHeight
  );
  const image = loadedImages.find((candidate) =>
    normalizedTarget
    && normalizeUrl(candidate.currentSrc || candidate.src || '') === normalizedTarget
  ) || loadedImages
    .sort((left, right) => (right.naturalWidth * right.naturalHeight) - (left.naturalWidth * left.naturalHeight))[0];
  if (!image) {
    return {
      ok: false,
      reason: 'no_loaded_image',
      url: normalizedTarget || normalizeUrl(document.location.href),
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
  const chosenUrl = normalizeUrl(image.currentSrc || image.src || normalizedTarget || document.location.href);
  const canvas = document.createElement('canvas');
  canvas.width = image.naturalWidth || image.width || 0;
  canvas.height = image.naturalHeight || image.height || 0;
  const context = canvas.getContext('2d');
  if (!context || !canvas.width || !canvas.height) {
    return {
      ok: false,
      reason: 'missing_canvas_context',
      url: chosenUrl,
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
  try {
    context.drawImage(image, 0, 0);
  } catch (error) {
    const classified = classifyCanvasError(error);
    return {
      ok: false,
      reason: classified.reason,
      error: classified.error,
      url: chosenUrl,
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
  try {
    const dataUrl = canvas.toDataURL('image/png');
    const bodyB64 = String(dataUrl || '').split(',', 2)[1] || '';
    if (!bodyB64) {
      return {
        ok: false,
        reason: 'canvas_serialization_failed',
        url: chosenUrl,
        title: document.title || '',
        contentType: document.contentType || '',
      };
    }
    return {
      ok: true,
      status: 200,
      url: chosenUrl,
      contentType: 'image/png',
      bodyB64,
      width: image.naturalWidth || canvas.width,
      height: image.naturalHeight || canvas.height,
    };
  } catch (error) {
    const classified = classifyCanvasError(error);
    return {
      ok: false,
      reason: classified.reason,
      error: classified.error,
      url: chosenUrl,
      title: document.title || '',
      contentType: document.contentType || '',
    };
  }
}
"""

__all__ = [
    "BrowserWorkflowBootstrapResult",
    "BrowserWorkflowClient",
    "FlareSolverrFailure",
    "PdfFallbackFailure",
    "ProviderBrowserProfile",
    "SciencePnasHtmlFailure",
    "bootstrap_browser_workflow",
    "browser_workflow_article_from_payload",
    "build_browser_workflow_html_candidates",
    "build_browser_workflow_pdf_candidates",
    "ensure_runtime_ready",
    "extract_pdf_url_from_crossref",
    "extract_science_pnas_markdown",
    "fetch_html_with_flaresolverr",
    "fetch_seeded_browser_pdf_payload",
    "load_runtime_config",
    "merge_browser_context_seeds",
    "merge_provider_owned_authors",
    "preferred_html_candidate_from_landing_page",
    "probe_runtime_status",
    "rewrite_inline_figure_links",
    "warm_browser_context_with_flaresolverr",
]


@dataclass
class BrowserWorkflowBootstrapResult:
    normalized_doi: str
    runtime: Any | None
    landing_page_url: str | None
    html_candidates: list[str]
    pdf_candidates: list[str]
    browser_context_seed: Mapping[str, Any] | None = None
    html_failure_reason: str | None = None
    html_failure_message: str | None = None
    html_payload: RawFulltextPayload | None = None
    runtime_failure: ProviderFailure | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderBrowserProfile:
    name: str
    article_source_name: str | None
    label: str
    hosts: tuple[str, ...]
    base_hosts: tuple[str, ...]
    html_path_templates: tuple[str, ...]
    pdf_path_templates: tuple[str, ...]
    crossref_pdf_position: int
    extract_markdown: Callable[..., tuple[str, dict[str, Any]]]
    fallback_author_extractor: Callable[[str], list[str]] | None
    shared_playwright_image_fetcher: bool


def preferred_html_candidate_from_landing_page(
    publisher: str,
    doi: str,
    landing_page_url: str | None,
) -> str | None:
    """Backward-compatible provider-name wrapper for legacy imports."""

    from ._science_pnas_profiles import preferred_html_candidate_from_landing_page as legacy_preferred

    return legacy_preferred(publisher, doi, landing_page_url)


def _looks_like_pdf_navigation_url(url: str | None) -> bool:
    normalized = normalize_text(url).lower()
    if not normalized:
        return False
    return any(token in normalized for token in ("/doi/pdf", "/doi/pdfdirect", "/doi/epdf", "/fullpdf", ".pdf"))


def _choose_playwright_seed_url(*candidates: str | None) -> str | None:
    normalized_candidates = [normalize_text(candidate) for candidate in candidates if normalize_text(candidate)]
    for candidate in normalized_candidates:
        if not _looks_like_pdf_navigation_url(candidate):
            return candidate
    return normalized_candidates[0] if normalized_candidates else None


def _image_magic_type(body: bytes | bytearray | None) -> str:
    return image_mime_type_from_bytes(body)


def _decode_base64_bytes(payload: str | None) -> bytes | None:
    normalized = normalize_text(payload)
    if not normalized:
        return None
    try:
        return base64.b64decode(normalized, validate=True)
    except Exception:
        return None


def _normalized_response_headers(headers: Mapping[str, Any] | None) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        return {}
    return {
        normalize_text(str(key)).lower(): str(value)
        for key, value in headers.items()
        if normalize_text(str(key))
    }


def _looks_like_image_response_payload(
    content_type: str | None,
    body: bytes | bytearray | None,
    source_url: str | None,
) -> bool:
    normalized_content_type = normalize_text(content_type).split(";", 1)[0].lower()
    magic_type = _image_magic_type(body)
    if normalized_content_type.startswith("image/"):
        return bool(magic_type)
    if magic_type:
        return True
    return False


def _looks_like_cloudflare_challenge_title(title: str | None) -> bool:
    normalized = normalize_text(title).lower()
    return bool(normalized and any(token in normalized for token in _CLOUDFLARE_CHALLENGE_TITLE_TOKENS))


def _html_text_snippet(body: bytes | bytearray | None, *, limit: int = 240) -> str:
    if not isinstance(body, (bytes, bytearray)) or not body:
        return ""
    try:
        decoded = bytes(body[:4096]).decode("utf-8", errors="replace")
    except Exception:
        return ""
    text = re.sub(r"<[^>]+>", " ", decoded)
    return normalize_text(html_lib.unescape(text))[:limit]


def _html_title_snippet(body: bytes | bytearray | None, *, limit: int = 160) -> str:
    if not isinstance(body, (bytes, bytearray)) or not body:
        return ""
    try:
        decoded = bytes(body[:8192]).decode("utf-8", errors="replace")
    except Exception:
        return ""
    match = re.search(r"<title\b[^>]*>(.*?)</title>", decoded, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return normalize_text(html_lib.unescape(re.sub(r"<[^>]+>", " ", match.group(1))))[:limit]


def _looks_like_cloudflare_challenge_failure(failure: Mapping[str, Any] | None) -> bool:
    if not isinstance(failure, Mapping):
        return False
    reason = normalize_text(str(failure.get("reason") or "")).lower()
    title = normalize_text(str(failure.get("title_snippet") or failure.get("title") or "")).lower()
    body = normalize_text(str(failure.get("body_snippet") or "")).lower()
    return (
        reason in {"cloudflare_challenge", "login_or_access_html"}
        or _looks_like_cloudflare_challenge_title(title)
        or any(token in body for token in _CLOUDFLARE_CHALLENGE_TITLE_TOKENS)
    )


def _compact_failure_diagnostic(values: Mapping[str, Any]) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            continue
        if isinstance(value, str):
            normalized = normalize_text(value)
            if normalized:
                diagnostic[key] = normalized
            continue
        if isinstance(value, (bool, int, float)):
            diagnostic[key] = value
            continue
        if isinstance(value, list) and value:
            diagnostic[key] = value
            continue
        if isinstance(value, Mapping) and value:
            diagnostic[key] = dict(value)
    return diagnostic


def _normalized_recovered_image_payload(
    payload: Any,
    *,
    fallback_url: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    body = payload.get("body")
    if not isinstance(body, (bytes, bytearray)) or not body:
        return None
    headers = payload.get("headers") if isinstance(payload.get("headers"), Mapping) else {}
    normalized_headers = _normalized_response_headers(headers)
    content_type = normalized_headers.get("content-type", "")
    final_url = normalize_text(str(payload.get("url") or "")) or fallback_url
    if not _looks_like_image_response_payload(content_type, body, final_url):
        return None
    normalized_payload = dict(payload)
    normalized_payload["status_code"] = int(payload.get("status_code") or 200)
    normalized_payload["headers"] = dict(normalized_headers)
    normalized_payload["body"] = bytes(body)
    normalized_payload["url"] = final_url
    return normalized_payload


def _copy_image_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    copied = dict(payload)
    body = payload.get("body")
    if isinstance(body, (bytes, bytearray)):
        copied["body"] = bytes(body)
    headers = payload.get("headers")
    if isinstance(headers, Mapping):
        copied["headers"] = dict(headers)
    dimensions = payload.get("dimensions")
    if isinstance(dimensions, Mapping):
        copied["dimensions"] = dict(dimensions)
    return copied


def _copy_failure_diagnostic(values: Mapping[str, Any]) -> dict[str, Any]:
    copied = dict(values)
    recovery_attempts = values.get("recovery_attempts")
    if isinstance(recovery_attempts, list):
        copied["recovery_attempts"] = [
            dict(item) if isinstance(item, Mapping) else item
            for item in recovery_attempts
        ]
    return copied


def _flaresolverr_image_payload_failure_reason(result: FetchedPublisherHtml) -> str:
    if not isinstance(result.image_payload, Mapping):
        return "flaresolverr_image_payload_missing"
    payload_reason = normalize_text(str(result.image_payload.get("reason") or ""))
    if payload_reason:
        return payload_reason
    return "flaresolverr_image_payload_invalid"


def _is_timeout_error(value: str | None) -> bool:
    normalized = normalize_text(value).lower()
    return bool(normalized and ("timeout" in normalized or "aborterror" in normalized))


def _image_fetch_failure_reason(*, error: str | None = None, timed_out: bool = False) -> str:
    if timed_out or _is_timeout_error(error):
        return "image_fetch_timeout"
    return "image_fetch_error"


def _flaresolverr_image_document_payload(result: FetchedPublisherHtml) -> dict[str, Any] | None:
    direct_payload = _payload_from_flaresolverr_image_payload(
        result.image_payload,
        fallback_url=result.final_url or result.source_url,
    )
    if direct_payload is not None:
        return direct_payload
    return None


def _payload_from_flaresolverr_image_payload(
    payload: Mapping[str, Any] | None,
    *,
    fallback_url: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    body = _decode_base64_bytes(str(payload.get("bodyB64") or ""))
    content_type = normalize_text(str(payload.get("contentType") or "")) or "image/png"
    final_url = normalize_text(str(payload.get("url") or "")) or fallback_url
    if body is None or not _looks_like_image_response_payload(content_type, body, final_url):
        return None
    try:
        width = int(payload.get("width") or 0)
        height = int(payload.get("height") or 0)
    except (TypeError, ValueError):
        width = height = 0
    return {
        "status_code": int(payload.get("status") or 200),
        "headers": {"content-type": content_type},
        "body": body,
        "url": final_url,
        "dimensions": {"width": width, "height": height},
    }


class _SharedPlaywrightImageDocumentFetcher:
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        min_width: int = 80,
        min_height: int = 80,
        challenge_recovery: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self._browser_context_seed_getter = browser_context_seed_getter
        self._seed_urls_getter = seed_urls_getter
        self._browser_user_agent = browser_user_agent
        self._headless = headless
        self._min_width = min_width
        self._min_height = min_height
        self._challenge_recovery = challenge_recovery
        self._playwright_manager = None
        self._browser = None
        self._context = None
        self._page = None
        self._warmed_seed_urls: set[str] = set()
        self._last_failure_by_url: dict[str, dict[str, Any]] = {}
        self._recovery_attempts_by_url: dict[str, list[dict[str, Any]]] = {}
        self._recovered_payload_by_url: dict[str, dict[str, Any]] = {}

    def __call__(self, image_url: str, _asset: Mapping[str, Any]) -> dict[str, Any] | None:
        normalized_url = normalize_text(image_url)
        if not normalized_url:
            return None
        page = self._ensure_page()
        if page is None:
            return None

        self._sync_context_cookies()
        self._warm_seed_urls(force=False)
        recovered_from_challenge = False
        for attempt in range(3):
            result = self._fetch_with_page(normalized_url)
            if result is not None:
                return result
            failure = self.failure_for(normalized_url)
            if (
                not recovered_from_challenge
                and _looks_like_cloudflare_challenge_failure(failure)
                and self._attempt_challenge_recovery(normalized_url, _asset, failure or {})
            ):
                recovered_payload = self._recovered_payload_by_url.get(normalized_url)
                if recovered_payload is not None:
                    return dict(recovered_payload)
                recovered_from_challenge = True
                continue
            if attempt == 0:
                self._sync_context_cookies()
                self._warm_seed_urls(force=True)
                continue
            break
        return None

    def failure_for(self, image_url: str) -> dict[str, Any] | None:
        diagnostic = self._last_failure_by_url.get(normalize_text(image_url))
        return dict(diagnostic) if diagnostic else None

    def close(self) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright_manager is not None:
            try:
                self._playwright_manager.stop()
            except Exception:
                pass
            self._playwright_manager = None

    def _current_seed(self) -> Mapping[str, Any]:
        seed = self._browser_context_seed_getter()
        return seed if isinstance(seed, Mapping) else {}

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return None

        active_user_agent = (
            normalize_text(self._current_seed().get("browser_user_agent"))
            or normalize_text(self._browser_user_agent)
            or build_user_agent({})
        )
        try:
            self._playwright_manager = sync_playwright().start()
            self._browser = self._playwright_manager.chromium.launch(headless=self._headless)
            self._context = self._browser.new_context(
                user_agent=active_user_agent,
                locale="en-US",
                viewport={"width": 1440, "height": 1600},
            )
            self._sync_context_cookies()
            self._page = self._context.new_page()
        except Exception:
            self.close()
            return None
        return self._page

    def _sync_context_cookies(self) -> None:
        if self._context is None:
            return
        cookies = list(self._current_seed().get("browser_cookies") or [])
        if not cookies:
            return
        try:
            self._context.add_cookies(cookies)
        except Exception:
            pass

    def _seed_urls(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in self._seed_urls_getter() or []:
            normalized = normalize_text(candidate)
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    def _warm_seed_urls(self, *, force: bool) -> None:
        page = self._page
        if page is None:
            return
        for seed_url in self._seed_urls():
            if not force and seed_url in self._warmed_seed_urls:
                continue
            try:
                page.goto(seed_url, wait_until="domcontentloaded", timeout=30000)
                self._warmed_seed_urls.add(seed_url)
            except Exception:
                continue

    def _record_failure(self, image_url: str, **values: Any) -> None:
        normalized_url = normalize_text(image_url)
        if not normalized_url:
            return
        diagnostic = _compact_failure_diagnostic({"source_url": normalized_url, **values})
        recovery_attempts = self._recovery_attempts_by_url.get(normalized_url) or []
        if recovery_attempts:
            diagnostic["recovery_attempts"] = list(recovery_attempts)
        if diagnostic:
            self._last_failure_by_url[normalized_url] = diagnostic

    def _record_response_failure(
        self,
        image_url: str,
        *,
        status: int | None,
        content_type: str,
        final_url: str,
        body: bytes | bytearray | None,
        title: str | None = None,
        reason: str = "non_image_response",
        canvas_error: str | None = None,
    ) -> None:
        title_snippet = normalize_text(title)[:160] or _html_title_snippet(body)
        body_snippet = _html_text_snippet(body)
        failure_reason = (
            "cloudflare_challenge"
            if _looks_like_cloudflare_challenge_title(title_snippet)
            or any(token in body_snippet.lower() for token in _CLOUDFLARE_CHALLENGE_TITLE_TOKENS)
            else reason
        )
        self._record_failure(
            image_url,
            status=status,
            content_type=content_type,
            final_url=final_url,
            title_snippet=title_snippet,
            body_snippet=body_snippet,
            reason=failure_reason,
            canvas_error=normalize_text(canvas_error),
        )

    def _attempt_challenge_recovery(
        self,
        image_url: str,
        asset: Mapping[str, Any],
        failure: Mapping[str, Any],
    ) -> bool:
        if self._challenge_recovery is None:
            return False
        try:
            recovery = self._challenge_recovery(image_url, asset, failure)
        except Exception as exc:
            recovery = {
                "status": "error",
                "reason": normalize_text(str(exc)) or exc.__class__.__name__,
            }
        if not isinstance(recovery, Mapping):
            return False
        recovered_payload = _normalized_recovered_image_payload(recovery.get("image_payload"), fallback_url=image_url)
        if recovered_payload is not None:
            self._recovered_payload_by_url[image_url] = recovered_payload
        diagnostic_recovery = {key: value for key, value in recovery.items() if key != "image_payload"}
        if (
            normalize_text(str(diagnostic_recovery.get("status") or "")).lower() != "ok"
            and not normalize_text(str(diagnostic_recovery.get("reason") or ""))
        ):
            diagnostic_recovery["reason"] = "challenge_recovery_failed"
        compact = _compact_failure_diagnostic(diagnostic_recovery)
        if compact:
            self._recovery_attempts_by_url.setdefault(image_url, []).append(compact)
            previous = self.failure_for(image_url) or {}
            self._record_failure(image_url, **previous)
        if normalize_text(str(recovery.get("status") or "")).lower() != "ok":
            return False
        self._sync_context_cookies()
        self._warm_seed_urls(force=True)
        return True

    def _fetch_with_page(self, image_url: str) -> dict[str, Any] | None:
        page = self._page
        if page is None:
            return None
        request_payload = self._payload_from_context_request(image_url)
        if request_payload is not None:
            return request_payload

        fetched_payload = self._payload_from_page_fetch_url(page, image_url)
        if fetched_payload is not None:
            return fetched_payload

        navigation_response = None
        try:
            navigation_response = page.goto(image_url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            navigation_response = None

        direct_payload = self._payload_from_navigation_response(navigation_response, fallback_url=image_url)
        if direct_payload is not None:
            return direct_payload

        image_info = self._wait_for_primary_image(page, image_url)
        if image_info is None:
            return None

        return self._payload_from_page_fetch(page, image_info)

    def _payload_from_context_request(self, image_url: str) -> dict[str, Any] | None:
        if self._context is None:
            return None
        try:
            response = self._context.request.get(
                image_url,
                headers={"Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"},
                timeout=60000,
            )
        except Exception as exc:
            self._record_failure(
                image_url,
                reason=_image_fetch_failure_reason(error=str(exc)),
                canvas_error=normalize_text(str(exc)),
            )
            return None
        return self._payload_from_response_body(response, fallback_url=image_url, attempted_url=image_url)

    def _payload_from_navigation_response(self, response: Any, *, fallback_url: str) -> dict[str, Any] | None:
        if response is None:
            return None
        return self._payload_from_response_body(response, fallback_url=fallback_url, attempted_url=fallback_url)

    def _payload_from_response_body(self, response: Any, *, fallback_url: str, attempted_url: str) -> dict[str, Any] | None:
        try:
            headers = _normalized_response_headers(response.all_headers())
        except Exception:
            headers = _normalized_response_headers(getattr(response, "headers", {}) or {})
        content_type = headers.get("content-type", "")
        final_url = normalize_text(getattr(response, "url", "") or "") or fallback_url
        status = int(getattr(response, "status", 0) or 0) or None
        try:
            body = response.body()
        except Exception:
            body = b""
        if not isinstance(body, (bytes, bytearray)) or not body:
            self._record_failure(
                attempted_url,
                status=status,
                content_type=content_type,
                final_url=final_url,
                reason="empty_response_body",
            )
            return None
        if not _looks_like_image_response_payload(content_type, body, final_url):
            self._record_response_failure(
                attempted_url,
                status=status,
                content_type=content_type,
                final_url=final_url,
                body=body,
            )
            return None
        payload: dict[str, Any] = {
            "status_code": int(getattr(response, "status", 200) or 200),
            "headers": headers,
            "body": bytes(body),
            "url": final_url,
        }
        return payload

    def _wait_for_primary_image(self, page: Any, image_url: str) -> dict[str, Any] | None:
        deadline = time.monotonic() + 15.0
        last_info: Mapping[str, Any] | None = None
        while time.monotonic() < deadline:
            try:
                image_info = page.evaluate(
                    """
                    ([minWidth, minHeight]) => {
                      const images = Array.from(document.images || []);
                      const best = images
                        .filter((image) =>
                          image.complete
                          && image.naturalWidth >= minWidth
                          && image.naturalHeight >= minHeight
                        )
                        .sort((left, right) => (right.naturalWidth * right.naturalHeight) - (left.naturalWidth * left.naturalHeight))[0];
                      if (!best) {
                        return {
                          ready: false,
                          imageCount: images.length,
                          title: document.title || '',
                          contentType: document.contentType || '',
                        };
                      }
                      return {
                        ready: true,
                        src: best.currentSrc || best.src || '',
                        width: best.naturalWidth || 0,
                        height: best.naturalHeight || 0,
                        imageCount: images.length,
                        title: document.title || '',
                        contentType: document.contentType || '',
                      };
                    }
                    """,
                    [self._min_width, self._min_height],
                )
            except Exception:
                return None
            if isinstance(image_info, Mapping):
                last_info = image_info
            if isinstance(image_info, Mapping) and image_info.get("ready"):
                return dict(image_info)
            if isinstance(image_info, Mapping) and _looks_like_cloudflare_challenge_title(
                str(image_info.get("title") or "")
            ):
                self._record_failure(
                    image_url,
                    content_type=normalize_text(str(image_info.get("contentType") or "")),
                    final_url=normalize_text(str(getattr(page, "url", "") or image_url)),
                    title_snippet=normalize_text(str(image_info.get("title") or ""))[:160],
                    reason="cloudflare_challenge",
                )
                return None
            try:
                page.wait_for_timeout(500)
            except Exception:
                break
        self._record_failure(
            image_url,
            content_type=normalize_text(str((last_info or {}).get("contentType") or "")),
            final_url=normalize_text(str(getattr(page, "url", "") or image_url)),
            title_snippet=normalize_text(str((last_info or {}).get("title") or ""))[:160],
            reason="no_loaded_image",
        )
        return None

    def _payload_from_page_fetch_url(
        self,
        page: Any,
        image_url: str,
        *,
        dimensions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        image_src = normalize_text(str(image_url or ""))
        if not image_src:
            return None
        try:
            fetched = page.evaluate(
                """
                async ([imageSrc, timeoutMs]) => {
                  const bytesToBase64 = (bytes) => {
                    let binary = '';
                    const chunkSize = 0x8000;
                    for (let index = 0; index < bytes.length; index += chunkSize) {
                      const chunk = bytes.subarray(index, index + chunkSize);
                      binary += String.fromCharCode(...chunk);
                    }
                    return btoa(binary);
                  };
                  const controller = new AbortController();
                  const timer = setTimeout(() => controller.abort(), timeoutMs);
                  const titleFromHtml = (text) => {
                    const match = String(text || '').match(/<title\\b[^>]*>([\\s\\S]*?)<\\/title>/i);
                    return match ? match[1].replace(/<[^>]+>/g, ' ').trim() : '';
                  };
                  try {
                    const response = await fetch(imageSrc, {
                      credentials: 'include',
                      cache: 'no-store',
                      signal: controller.signal,
                    });
                    const contentType = response.headers.get('content-type') || '';
                    const normalizedContentType = contentType.split(';', 1)[0].trim().toLowerCase();
                    if (
                      normalizedContentType
                      && !normalizedContentType.startsWith('image/')
                      && normalizedContentType !== 'application/octet-stream'
                    ) {
                      let bodySnippet = '';
                      try {
                        bodySnippet = (await response.clone().text()).slice(0, 500);
                      } catch (error) {}
                      return {
                        ok: response.ok,
                        status: response.status,
                        url: response.url || imageSrc,
                        contentType,
                        nonImage: true,
                        title: titleFromHtml(bodySnippet) || document.title || '',
                        bodySnippet,
                      };
                    }
                    const buffer = await response.arrayBuffer();
                    const bytes = new Uint8Array(buffer);
                    return {
                      ok: response.ok,
                      status: response.status,
                      url: response.url || imageSrc,
                      contentType,
                      bodyB64: bytesToBase64(bytes),
                    };
                  } catch (error) {
                    return {
                      ok: false,
                      error: String((error && (error.name || error.message)) || error || ''),
                      timedOut: error && error.name === 'AbortError',
                    };
                  } finally {
                    clearTimeout(timer);
                  }
                }
                """,
                [image_src, _IMAGE_DOCUMENT_FETCH_TIMEOUT_MS],
            )
        except Exception:
            return None
        if not isinstance(fetched, Mapping):
            return None
        body = _decode_base64_bytes(str(fetched.get("bodyB64") or ""))
        final_url = normalize_text(str(fetched.get("url") or "")) or image_src
        content_type = normalize_text(str(fetched.get("contentType") or ""))
        if body is None or not _looks_like_image_response_payload(content_type, body, final_url):
            fallback_body = body
            if fallback_body is None:
                fallback_body = str(fetched.get("bodySnippet") or "").encode("utf-8", errors="replace")
            failure_reason = (
                "non_image_response"
                if fetched.get("nonImage")
                else _image_fetch_failure_reason(
                    error=str(fetched.get("error") or ""),
                    timed_out=bool(fetched.get("timedOut")),
                )
            )
            self._record_response_failure(
                image_src,
                status=int(fetched.get("status") or 0) or None,
                content_type=content_type,
                final_url=final_url,
                body=fallback_body,
                title=normalize_text(str(fetched.get("title") or "")),
                reason=failure_reason,
                canvas_error=normalize_text(str(fetched.get("error") or "")),
            )
            return None
        return {
            "status_code": int(fetched.get("status") or 200),
            "headers": {"content-type": content_type},
            "body": body,
            "url": final_url,
            "dimensions": {
                "width": int((dimensions or {}).get("width") or 0),
                "height": int((dimensions or {}).get("height") or 0),
            },
        }

    def _payload_from_page_fetch(self, page: Any, image_info: Mapping[str, Any]) -> dict[str, Any] | None:
        payload = self._payload_from_page_fetch_url(
            page,
            normalize_text(str(image_info.get("src") or "")),
            dimensions=image_info,
        )
        if payload is not None:
            return payload
        return self._payload_from_loaded_image(page, image_info)

    def _payload_from_loaded_image(self, page: Any, image_info: Mapping[str, Any]) -> dict[str, Any] | None:
        image_src = normalize_text(str(image_info.get("src") or ""))
        if not image_src:
            return None
        try:
            rendered = page.evaluate(
                _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
                [image_src, self._min_width, self._min_height],
            )
        except Exception:
            return None
        if not isinstance(rendered, Mapping):
            return None
        body = _decode_base64_bytes(str(rendered.get("bodyB64") or ""))
        final_url = normalize_text(str(rendered.get("url") or "")) or image_src
        content_type = normalize_text(str(rendered.get("contentType") or "")) or "image/png"
        if not rendered.get("ok") or body is None or not _looks_like_image_response_payload(content_type, body, final_url):
            previous = self.failure_for(image_src) or {}
            failure_values = {
                **previous,
                "final_url": final_url,
                "title_snippet": normalize_text(str(rendered.get("title") or ""))[:160],
                "content_type": content_type,
                "reason": normalize_text(str(rendered.get("reason") or "")) or "canvas_serialization_failed",
                "canvas_error": normalize_text(str(rendered.get("error") or "")),
            }
            self._record_failure(
                image_src,
                **failure_values,
            )
            return None
        return {
            "status_code": int(rendered.get("status") or 200),
            "headers": {"content-type": content_type},
            "body": body,
            "url": final_url,
            "dimensions": {
                "width": int(rendered.get("width") or image_info.get("width") or 0),
                "height": int(rendered.get("height") or image_info.get("height") or 0),
            },
        }


class _ThreadLocalSharedPlaywrightImageDocumentFetcher:
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        min_width: int = 80,
        min_height: int = 80,
        challenge_recovery: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self._browser_context_seed_getter = browser_context_seed_getter
        self._seed_urls_getter = seed_urls_getter
        self._browser_user_agent = browser_user_agent
        self._headless = headless
        self._min_width = min_width
        self._min_height = min_height
        self._challenge_recovery = challenge_recovery
        self._thread_local = threading.local()
        self._lock = threading.Lock()
        self._fetchers: list[_SharedPlaywrightImageDocumentFetcher] = []

    def _get_fetcher(self) -> _SharedPlaywrightImageDocumentFetcher:
        fetcher = getattr(self._thread_local, "fetcher", None)
        if isinstance(fetcher, _SharedPlaywrightImageDocumentFetcher):
            return fetcher
        fetcher = _SharedPlaywrightImageDocumentFetcher(
            browser_context_seed_getter=self._browser_context_seed_getter,
            seed_urls_getter=self._seed_urls_getter,
            browser_user_agent=self._browser_user_agent,
            headless=self._headless,
            min_width=self._min_width,
            min_height=self._min_height,
            challenge_recovery=self._challenge_recovery,
        )
        self._thread_local.fetcher = fetcher
        with self._lock:
            self._fetchers.append(fetcher)
        emit_structured_log(
            logger,
            logging.DEBUG,
            "browser_workflow_image_fetcher_thread_created",
            thread=threading.current_thread().name,
        )
        return fetcher

    def __call__(self, image_url: str, asset: Mapping[str, Any]) -> dict[str, Any] | None:
        return self._get_fetcher()(image_url, asset)

    def failure_for(self, image_url: str) -> dict[str, Any] | None:
        fetcher = getattr(self._thread_local, "fetcher", None)
        if not isinstance(fetcher, _SharedPlaywrightImageDocumentFetcher):
            return None
        return fetcher.failure_for(image_url)

    def close(self) -> None:
        with self._lock:
            fetchers = list(self._fetchers)
            self._fetchers.clear()
        for fetcher in fetchers:
            fetcher.close()


class _MemoizedImageDocumentFetcher:
    def __init__(self, fetcher: Any) -> None:
        self._fetcher = fetcher
        self._lock = threading.Lock()
        self._payload_by_url: dict[str, dict[str, Any]] = {}
        self._failure_by_url: dict[str, dict[str, Any]] = {}
        self._inflight_by_url: dict[str, Future[dict[str, Any] | None]] = {}

    def __call__(self, image_url: str, asset: Mapping[str, Any]) -> dict[str, Any] | None:
        normalized_url = normalize_text(image_url)
        if not normalized_url:
            return self._fetcher(image_url, asset)
        with self._lock:
            cached_payload = self._payload_by_url.get(normalized_url)
            if cached_payload is not None:
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_image_candidate_cache",
                    state="hit_payload",
                    url=normalized_url,
                )
                return _copy_image_payload(cached_payload)
            if normalized_url in self._failure_by_url:
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_image_candidate_cache",
                    state="hit_failure",
                    url=normalized_url,
                )
                return None
            future = self._inflight_by_url.get(normalized_url)
            if future is None:
                future = Future()
                self._inflight_by_url[normalized_url] = future
                owner = True
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_image_candidate_cache",
                    state="miss",
                    url=normalized_url,
                )
            else:
                owner = False
        if not owner:
            payload = future.result()
            return _copy_image_payload(payload) if payload is not None else None

        try:
            payload = self._fetcher(normalized_url, asset)
            copied_payload = _copy_image_payload(payload) if isinstance(payload, Mapping) else None
            reporter = getattr(self._fetcher, "failure_for", None)
            failure = reporter(normalized_url) if callable(reporter) else None
            copied_failure = _copy_failure_diagnostic(failure) if isinstance(failure, Mapping) else None
            if copied_payload is None and copied_failure is None:
                copied_failure = {"source_url": normalized_url, "reason": "image_fetch_error"}
        except Exception as exc:
            with self._lock:
                future = self._inflight_by_url.pop(normalized_url)
            future.set_exception(exc)
            raise

        with self._lock:
            if copied_payload is not None:
                self._payload_by_url[normalized_url] = copied_payload
            else:
                self._failure_by_url[normalized_url] = copied_failure or {
                    "source_url": normalized_url,
                    "reason": "image_fetch_error",
                }
            future = self._inflight_by_url.pop(normalized_url)
        future.set_result(copied_payload)
        return _copy_image_payload(copied_payload) if copied_payload is not None else None

    def failure_for(self, image_url: str) -> dict[str, Any] | None:
        normalized_url = normalize_text(image_url)
        with self._lock:
            cached_failure = self._failure_by_url.get(normalized_url)
            if cached_failure is not None:
                return _copy_failure_diagnostic(cached_failure)
            cached_payload = self._payload_by_url.get(normalized_url)
            if cached_payload is not None:
                return None
        reporter = getattr(self._fetcher, "failure_for", None)
        if not callable(reporter):
            return None
        failure = reporter(normalized_url)
        return _copy_failure_diagnostic(failure) if isinstance(failure, Mapping) else None

    def close(self) -> None:
        close_fetcher = getattr(self._fetcher, "close", None)
        if callable(close_fetcher):
            close_fetcher()


class _MemoizedFigurePageFetcher:
    def __init__(self, fetcher: Callable[[str], tuple[str, str] | None]) -> None:
        self._fetcher = fetcher
        self._lock = threading.Lock()
        self._values_by_url: dict[str, tuple[str, str] | None] = {}
        self._inflight_by_url: dict[str, Future[tuple[str, str] | None]] = {}

    def __call__(self, figure_page_url: str) -> tuple[str, str] | None:
        normalized_url = normalize_text(figure_page_url)
        if not normalized_url:
            return None
        with self._lock:
            if normalized_url in self._values_by_url:
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_figure_page_cache",
                    state="hit",
                    url=normalized_url,
                )
                return self._values_by_url[normalized_url]
            future = self._inflight_by_url.get(normalized_url)
            if future is None:
                future = Future()
                self._inflight_by_url[normalized_url] = future
                owner = True
                emit_structured_log(
                    logger,
                    logging.DEBUG,
                    "browser_workflow_figure_page_cache",
                    state="miss",
                    url=normalized_url,
                )
            else:
                owner = False
        if not owner:
            return future.result()

        try:
            value = self._fetcher(normalized_url)
        except Exception as exc:
            with self._lock:
                future = self._inflight_by_url.pop(normalized_url)
            future.set_exception(exc)
            raise

        with self._lock:
            self._values_by_url[normalized_url] = value
            future = self._inflight_by_url.pop(normalized_url)
        future.set_result(value)
        return value


class _SharedPlaywrightFileDocumentFetcher:
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        challenge_recovery: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
    ) -> None:
        self._browser_context_seed_getter = browser_context_seed_getter
        self._seed_urls_getter = seed_urls_getter
        self._browser_user_agent = browser_user_agent
        self._headless = headless
        self._challenge_recovery = challenge_recovery
        self._playwright_manager = None
        self._browser = None
        self._context = None
        self._page = None
        self._warmed_seed_urls: set[str] = set()
        self._last_failure_by_url: dict[str, dict[str, Any]] = {}
        self._recovery_attempts_by_url: dict[str, list[dict[str, Any]]] = {}

    def __call__(self, file_url: str, asset: Mapping[str, Any]) -> dict[str, Any] | None:
        normalized_url = normalize_text(file_url)
        if not normalized_url:
            return None
        if self._ensure_context() is None:
            return None

        self._sync_context_cookies()
        self._warm_seed_urls(force=False)
        recovered_from_challenge = False
        for attempt in range(3):
            result = self._fetch_with_context_request(normalized_url)
            if result is not None:
                return result
            failure = self.failure_for(normalized_url)
            if (
                not recovered_from_challenge
                and _looks_like_cloudflare_challenge_failure(failure)
                and self._attempt_challenge_recovery(normalized_url, asset, failure or {})
            ):
                recovered_from_challenge = True
                continue
            if attempt == 0:
                self._sync_context_cookies()
                self._warm_seed_urls(force=True)
                continue
            break
        return None

    def failure_for(self, file_url: str) -> dict[str, Any] | None:
        diagnostic = self._last_failure_by_url.get(normalize_text(file_url))
        return dict(diagnostic) if diagnostic else None

    def close(self) -> None:
        if self._page is not None:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright_manager is not None:
            try:
                self._playwright_manager.stop()
            except Exception:
                pass
            self._playwright_manager = None

    def _current_seed(self) -> Mapping[str, Any]:
        seed = self._browser_context_seed_getter()
        return seed if isinstance(seed, Mapping) else {}

    def _ensure_context(self):
        if self._context is not None:
            return self._context
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return None

        active_user_agent = (
            normalize_text(self._current_seed().get("browser_user_agent"))
            or normalize_text(self._browser_user_agent)
            or build_user_agent({})
        )
        try:
            self._playwright_manager = sync_playwright().start()
            self._browser = self._playwright_manager.chromium.launch(headless=self._headless)
            self._context = self._browser.new_context(
                user_agent=active_user_agent,
                locale="en-US",
                viewport={"width": 1440, "height": 1600},
            )
            self._sync_context_cookies()
            self._page = self._context.new_page()
        except Exception:
            self.close()
            return None
        return self._context

    def _sync_context_cookies(self) -> None:
        if self._context is None:
            return
        cookies = list(self._current_seed().get("browser_cookies") or [])
        if not cookies:
            return
        try:
            self._context.add_cookies(cookies)
        except Exception:
            pass

    def _seed_urls(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in self._seed_urls_getter() or []:
            normalized = normalize_text(candidate)
            if normalized and normalized not in seen:
                seen.add(normalized)
                ordered.append(normalized)
        return ordered

    def _warm_seed_urls(self, *, force: bool) -> None:
        page = self._page
        if page is None:
            return
        for seed_url in self._seed_urls():
            if not force and seed_url in self._warmed_seed_urls:
                continue
            try:
                page.goto(seed_url, wait_until="domcontentloaded", timeout=30000)
                self._warmed_seed_urls.add(seed_url)
            except Exception:
                continue

    def _record_failure(self, file_url: str, **values: Any) -> None:
        normalized_url = normalize_text(file_url)
        if not normalized_url:
            return
        diagnostic = _compact_failure_diagnostic({"source_url": normalized_url, **values})
        recovery_attempts = self._recovery_attempts_by_url.get(normalized_url) or []
        if recovery_attempts:
            diagnostic["recovery_attempts"] = list(recovery_attempts)
        if diagnostic:
            self._last_failure_by_url[normalized_url] = diagnostic

    def _record_response_failure(
        self,
        file_url: str,
        *,
        status: int | None,
        content_type: str,
        final_url: str,
        body: bytes | bytearray | None,
        reason: str,
    ) -> None:
        self._record_failure(
            file_url,
            status=status,
            content_type=content_type,
            final_url=final_url,
            title_snippet=_html_title_snippet(body),
            body_snippet=_html_text_snippet(body),
            reason=reason,
        )

    def _attempt_challenge_recovery(
        self,
        file_url: str,
        asset: Mapping[str, Any],
        failure: Mapping[str, Any],
    ) -> bool:
        if self._challenge_recovery is None:
            return False
        try:
            recovery = self._challenge_recovery(file_url, asset, failure)
        except Exception as exc:
            recovery = {
                "status": "error",
                "reason": normalize_text(str(exc)) or exc.__class__.__name__,
            }
        if not isinstance(recovery, Mapping):
            return False
        compact = _compact_failure_diagnostic(recovery)
        if compact:
            self._recovery_attempts_by_url.setdefault(file_url, []).append(compact)
            previous = self.failure_for(file_url) or {}
            self._record_failure(file_url, **previous)
        if normalize_text(str(recovery.get("status") or "")).lower() != "ok":
            return False
        self._sync_context_cookies()
        self._warm_seed_urls(force=True)
        return True

    def _fetch_with_context_request(self, file_url: str) -> dict[str, Any] | None:
        if self._context is None:
            return None
        try:
            response = self._context.request.get(
                file_url,
                headers={"Accept": "*/*"},
                timeout=60000,
            )
        except Exception as exc:
            self._record_failure(
                file_url,
                reason=normalize_text(str(exc)) or exc.__class__.__name__,
            )
            return None

        try:
            headers = _normalized_response_headers(response.all_headers())
        except Exception:
            headers = _normalized_response_headers(getattr(response, "headers", {}) or {})
        content_type = headers.get("content-type", "")
        final_url = normalize_text(getattr(response, "url", "") or "") or file_url
        status = int(getattr(response, "status", 0) or 0) or None
        try:
            body = response.body()
        except Exception:
            body = b""
        if not isinstance(body, (bytes, bytearray)) or not body:
            self._record_failure(
                file_url,
                status=status,
                content_type=content_type,
                final_url=final_url,
                reason="empty_response_body",
            )
            return None
        block_reason = supplementary_response_block_reason(content_type, body)
        if block_reason:
            self._record_response_failure(
                file_url,
                status=status,
                content_type=content_type,
                final_url=final_url,
                body=body,
                reason=block_reason,
            )
            return None
        return {
            "status_code": int(getattr(response, "status", 200) or 200),
            "headers": headers,
            "body": bytes(body),
            "url": final_url,
        }


def _build_shared_playwright_image_fetcher(
    *,
    browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
    seed_urls_getter: Callable[[], list[str]],
    browser_user_agent: str | None = None,
    headless: bool = True,
    min_width: int = 80,
    min_height: int = 80,
    challenge_recovery: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
) -> _ThreadLocalSharedPlaywrightImageDocumentFetcher:
    return _ThreadLocalSharedPlaywrightImageDocumentFetcher(
        browser_context_seed_getter=browser_context_seed_getter,
        seed_urls_getter=seed_urls_getter,
        browser_user_agent=browser_user_agent,
        headless=headless,
        min_width=min_width,
        min_height=min_height,
        challenge_recovery=challenge_recovery,
    )


def _build_shared_playwright_file_fetcher(
    *,
    browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
    seed_urls_getter: Callable[[], list[str]],
    browser_user_agent: str | None = None,
    headless: bool = True,
    challenge_recovery: Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None] | None = None,
) -> _SharedPlaywrightFileDocumentFetcher:
    return _SharedPlaywrightFileDocumentFetcher(
        browser_context_seed_getter=browser_context_seed_getter,
        seed_urls_getter=seed_urls_getter,
        browser_user_agent=browser_user_agent,
        headless=headless,
        challenge_recovery=challenge_recovery,
    )


def fetch_image_document_with_playwright(
    image_url: str,
    *,
    browser_cookies: list[dict[str, Any]] | None = None,
    browser_user_agent: str | None = None,
    headless: bool = True,
    seed_urls: list[str] | None = None,
    min_width: int = 80,
    min_height: int = 80,
) -> dict[str, Any] | None:
    normalized_url = normalize_text(image_url)
    if not normalized_url:
        return None
    fetcher = _build_shared_playwright_image_fetcher(
        browser_context_seed_getter=lambda: {
            "browser_cookies": list(browser_cookies or []),
            "browser_user_agent": browser_user_agent,
            "browser_final_url": next(
                (normalize_text(candidate) for candidate in reversed(seed_urls or []) if normalize_text(candidate)),
                None,
            ),
        },
        seed_urls_getter=lambda: [normalize_text(url) for url in seed_urls or [] if normalize_text(url)],
        browser_user_agent=browser_user_agent,
        headless=headless,
        min_width=min_width,
        min_height=min_height,
    )
    try:
        return fetcher(normalized_url, {})
    except Exception:
        return None
    finally:
        fetcher.close()


def _leading_body_after_abstract(
    metadata_abstract: str | None,
    extracted_abstract: str | None,
) -> str | None:
    normalized_metadata = normalize_text(metadata_abstract)
    normalized_abstract = normalize_text(extracted_abstract)
    if not normalized_metadata or not normalized_abstract or normalized_metadata == normalized_abstract:
        return None
    if not normalized_metadata.startswith(normalized_abstract):
        return None
    remainder = normalized_metadata[len(normalized_abstract) :].strip()
    return remainder or None


def _prepend_leading_body_markdown(markdown_text: str, lead_body: str | None) -> str:
    normalized_lead_body = normalize_text(lead_body)
    if not normalized_lead_body:
        return markdown_text
    if normalized_lead_body in normalize_text(markdown_text):
        return markdown_text

    main_text_block = f"## Main Text\n\n{normalized_lead_body}"
    stripped_markdown = markdown_text.strip()
    if not stripped_markdown:
        return main_text_block
    if stripped_markdown.startswith("# "):
        parts = stripped_markdown.split("\n\n", 1)
        if len(parts) == 2:
            return f"{parts[0]}\n\n{main_text_block}\n\n{parts[1]}".strip()
    return f"{main_text_block}\n\n{stripped_markdown}".strip()


def _download_asset_result_key(asset: Mapping[str, Any]) -> str:
    key = normalize_text(html_asset_identity_key(asset))
    if key:
        return key
    parts = [
        normalize_text(str(asset.get("kind") or "")),
        normalize_text(str(asset.get("heading") or "")),
        normalize_text(str(asset.get("caption") or "")),
        normalize_text(str(asset.get("download_url") or "")),
        normalize_text(str(asset.get("source_url") or "")),
    ]
    return "|".join(part for part in parts if part)


def _download_asset_match_tokens(asset: Mapping[str, Any]) -> set[str]:
    tokens = {
        normalize_text(str(asset.get(field) or ""))
        for field in (
            "heading",
            "caption",
            "url",
            "download_url",
            "original_url",
            "source_url",
            "figure_page_url",
        )
    }
    return {token for token in tokens if token}


def _browser_workflow_image_download_candidates(
    _transport,
    *,
    asset: Mapping[str, Any],
    user_agent: str,
    figure_page_fetcher: Callable[[str], tuple[str, str] | None] | None = None,
) -> list[str]:
    del user_agent
    direct_full_size_url = normalize_text(str(asset.get("full_size_url") or ""))
    primary_url = normalize_text(str(asset.get("url") or ""))
    preview_url = normalize_text(str(asset.get("preview_url") or "")) or primary_url
    candidates: list[str] = []

    if direct_full_size_url:
        candidates.append(direct_full_size_url)

    figure_page_url = normalize_text(str(asset.get("figure_page_url") or ""))
    if figure_page_url and figure_page_fetcher is not None:
        try:
            page_result = figure_page_fetcher(figure_page_url)
        except Exception:
            page_result = None
        if page_result is not None:
            page_html, page_url = page_result
            full_size_url = extract_full_size_figure_image_url(page_html, page_url)
            if full_size_url:
                candidates.append(full_size_url)

    if primary_url and looks_like_full_size_asset_url(primary_url):
        candidates.append(primary_url)
    if preview_url:
        candidates.append(preview_url)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _merge_download_attempt_results(
    initial: Mapping[str, Any],
    retry: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    downloads_by_key: dict[str, dict[str, Any]] = {}
    for result in (initial, retry):
        for asset in list(result.get("assets") or []):
            key = _download_asset_result_key(asset)
            downloads_by_key[key or str(len(downloads_by_key))] = dict(asset)

    merged_downloads = list(downloads_by_key.values())
    resolved_tokens = set().union(*(_download_asset_match_tokens(asset) for asset in merged_downloads)) if merged_downloads else set()
    failure_candidates = list(retry.get("asset_failures") or []) or list(initial.get("asset_failures") or [])
    unresolved_failures = []
    for failure in failure_candidates:
        failure_tokens = {
            normalize_text(str(failure.get(field) or ""))
            for field in ("heading", "caption", "source_url")
        }
        failure_tokens = {token for token in failure_tokens if token}
        if failure_tokens and failure_tokens & resolved_tokens:
            continue
        unresolved_failures.append(dict(failure))

    return {
        "assets": merged_downloads,
        "asset_failures": unresolved_failures,
    }


def _normalized_authors(values: Any) -> list[str]:
    return [
        normalize_text(str(item))
        for item in (values or [])
        if normalize_text(str(item))
    ]


def merge_provider_owned_authors(
    metadata: Mapping[str, Any],
    raw_payload: RawFulltextPayload,
    *,
    fallback_extractor: Callable[[str], list[str]] | None = None,
) -> dict[str, Any]:
    article_metadata = dict(metadata)
    content = getattr(raw_payload, "content", None)
    extraction = content.diagnostics.get("extraction") if content is not None else None
    extracted_authors = _normalized_authors(
        extraction.get("extracted_authors") if isinstance(extraction, Mapping) else []
    )
    if not extracted_authors and fallback_extractor is not None and "html" in normalize_text(raw_payload.content_type).lower():
        html_text = bytes(raw_payload.body or b"").decode("utf-8", errors="replace")
        extracted_authors = _normalized_authors(fallback_extractor(html_text))
    if not extracted_authors:
        return article_metadata

    existing_authors = _normalized_authors(article_metadata.get("authors") or [])
    article_metadata["authors"] = dedupe_authors([*extracted_authors, *existing_authors])
    return article_metadata


def bootstrap_browser_workflow(
    client: "BrowserWorkflowClient",
    doi: str,
    metadata: ProviderMetadata,
    *,
    allow_runtime_failure: bool = False,
) -> BrowserWorkflowBootstrapResult:
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        raise ProviderFailure("not_supported", f"{client.name} full-text retrieval requires a DOI.")

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
        bool(preferred_html_candidate and html_candidates and html_candidates[0] == preferred_html_candidate),
        html_candidates[0] if html_candidates else None,
        len(html_candidates),
    )

    try:
        result.runtime = load_runtime_config(client.env, provider=client.name, doi=normalized_doi)
        ensure_runtime_ready(result.runtime)
    except ProviderFailure as exc:
        if not allow_runtime_failure:
            raise
        result.runtime_failure = exc
        result.html_failure_reason = exc.code
        result.html_failure_message = exc.message
        return result

    try:
        html_result = fetch_html_with_flaresolverr(html_candidates, publisher=client.name, config=result.runtime)
        result.browser_context_seed = html_result.browser_context_seed
        markdown_text, extraction = client.extract_markdown(
            html_result.html,
            html_result.final_url,
            metadata=metadata,
        )
        result.html_payload = RawFulltextPayload(
            provider=client.name,
            source_url=html_result.final_url,
            content_type="text/html",
            body=html_result.html.encode("utf-8"),
            content=ProviderContent(
                route_kind="html",
                source_url=html_result.final_url,
                content_type="text/html",
                body=html_result.html.encode("utf-8"),
                markdown_text=markdown_text,
                diagnostics={
                    "extraction": extraction,
                    "availability_diagnostics": extraction.get("availability_diagnostics"),
                },
                fetcher="flaresolverr",
                browser_context_seed=dict(result.browser_context_seed or {}),
            ),
            warnings=list(result.warnings),
            trace=trace_from_markers([f"fulltext:{client.name}_html_ok"]),
            needs_local_copy=False,
        )
        return result
    except FlareSolverrFailure as exc:
        result.browser_context_seed = exc.browser_context_seed or result.browser_context_seed
        result.html_failure_reason = exc.kind
        result.html_failure_message = exc.message
    except SciencePnasHtmlFailure as exc:
        result.html_failure_reason = exc.reason
        result.html_failure_message = exc.message

    return result


def fetch_seeded_browser_pdf_payload(
    *,
    provider: str,
    runtime,
    pdf_candidates: list[str],
    html_candidates: list[str],
    landing_page_url: str | None,
    user_agent: str,
    browser_context_seed: Mapping[str, Any] | None,
    html_failure_reason: str | None,
    html_failure_message: str | None,
    warnings: list[str] | None = None,
    success_source_trail: list[str] | None = None,
    success_warning: str = "Full text was extracted from PDF fallback after the HTML path was not usable.",
    artifact_subdir: str = "pdf_fallback",
) -> RawFulltextPayload:
    pdf_browser_context_seed = warm_browser_context_with_flaresolverr(
        pdf_candidates,
        publisher=provider,
        config=runtime,
        browser_context_seed=browser_context_seed,
    )
    seed_url = _choose_playwright_seed_url(
        (browser_context_seed or {}).get("browser_final_url"),
        html_candidates[0] if html_candidates else None,
        landing_page_url,
        pdf_browser_context_seed.get("browser_final_url"),
    )
    pdf_result = fetch_pdf_with_playwright(
        pdf_candidates,
        artifact_dir=runtime.artifact_dir / artifact_subdir,
        browser_cookies=list(pdf_browser_context_seed.get("browser_cookies") or []),
        browser_user_agent=pdf_browser_context_seed.get("browser_user_agent") or user_agent,
        headless=runtime.headless,
        seed_urls=[seed_url] if seed_url else None,
    )
    payload_warnings = [str(item) for item in warnings or [] if str(item).strip()]
    if success_warning:
        payload_warnings.append(success_warning)
    return RawFulltextPayload(
        provider=provider,
        source_url=pdf_result.final_url,
        content_type="application/pdf",
        body=pdf_result.pdf_bytes,
        content=ProviderContent(
            route_kind="pdf_fallback",
            source_url=pdf_result.final_url,
            content_type="application/pdf",
            body=pdf_result.pdf_bytes,
            markdown_text=pdf_result.markdown_text,
            html_failure_reason=html_failure_reason,
            html_failure_message=html_failure_message,
            suggested_filename=pdf_result.suggested_filename,
        ),
        warnings=payload_warnings,
        trace=trace_from_markers(list(success_source_trail or [])),
        needs_local_copy=True,
    )


def browser_workflow_article_from_payload(
    client: "BrowserWorkflowClient",
    metadata: ProviderMetadata,
    raw_payload: RawFulltextPayload,
    *,
    downloaded_assets: list[Mapping[str, Any]] | None = None,
    asset_failures: list[Mapping[str, Any]] | None = None,
):
    content = raw_payload.content
    markdown_text = str((content.markdown_text if content is not None else "") or "").strip()
    warnings = list(raw_payload.warnings)
    trace = list(raw_payload.trace)
    doi = normalize_doi(metadata.get("doi"))
    source = client.article_source()
    assets = list(downloaded_assets or [])
    content_type = str(raw_payload.content_type or "").lower()

    if not markdown_text and "html" in content_type:
        html_text = bytes(raw_payload.body or b"").decode("utf-8", errors="replace").strip()
        if html_text:
            try:
                markdown_text, extraction = client.extract_markdown(
                    html_text,
                    raw_payload.source_url or str(metadata.get("landing_page_url") or ""),
                    metadata=metadata,
                )
            except SciencePnasHtmlFailure as exc:
                warnings.append(f"{client.name} HTML content was not usable ({exc.message}).")
            else:
                diagnostics_payload = dict(content.diagnostics) if content is not None else {}
                diagnostics_payload["extraction"] = extraction
                diagnostics = extraction.get("availability_diagnostics")
                if diagnostics is not None:
                    diagnostics_payload["availability_diagnostics"] = diagnostics
                if content is not None:
                    raw_payload.content = replace(
                        content,
                        markdown_text=markdown_text,
                        diagnostics=diagnostics_payload,
                    )
                    content = raw_payload.content

    if not markdown_text:
        warnings.append(f"{client.name} retrieval did not produce usable markdown.")
        return metadata_only_article(
            source=source,
            metadata=metadata,
            doi=doi or None,
            warnings=warnings,
            trace=[*trace, *trace_from_markers([f"fulltext:{client.name}_parse_fail"])],
        )
    if asset_failures:
        warnings.append(f"{client.name} related assets were only partially downloaded ({len(asset_failures)} failed).")
    if assets and markdown_text:
        markdown_text = rewrite_inline_figure_links(
            markdown_text,
            figure_assets=assets,
            publisher=client.name,
        )

    article_metadata = dict(metadata)
    extraction_payload = content.diagnostics.get("extraction") if content is not None else None
    extracted_abstract = normalize_text(
        extraction_payload.get("abstract_text") if isinstance(extraction_payload, Mapping) else ""
    )
    extracted_references = (
        list(extraction_payload.get("references") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    abstract_sections = (
        list(extraction_payload.get("abstract_sections") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    section_hints = (
        list(extraction_payload.get("section_hints") or [])
        if isinstance(extraction_payload, Mapping)
        else []
    )
    if extracted_references:
        article_metadata["references"] = extracted_references
    if extracted_abstract:
        lead_body = _leading_body_after_abstract(article_metadata.get("abstract"), extracted_abstract)
        article_metadata["abstract"] = extracted_abstract
        markdown_text = _prepend_leading_body_markdown(markdown_text, lead_body)
    availability_diagnostics = (
        dict(content.diagnostics.get("availability_diagnostics") or {})
        if content is not None and isinstance(content.diagnostics.get("availability_diagnostics"), Mapping)
        else None
    )

    article = article_from_markdown(
        source=source,
        metadata=article_metadata,
        doi=doi or None,
        markdown_text=markdown_text,
        abstract_sections=abstract_sections,
        section_hints=section_hints,
        assets=assets,
        warnings=warnings,
        trace=trace,
        availability_diagnostics=availability_diagnostics,
        allow_downgrade_from_diagnostics=True,
    )
    article.quality.asset_failures = coerce_asset_failure_diagnostics(asset_failures)
    return article


def _finalize_abstract_only_provider_article(
    provider_name: str,
    article,
    *,
    warnings: list[str] | None = None,
):
    marker = f"fulltext:{provider_name}_abstract_only"
    article.quality.trace = merge_trace(article.quality.trace, trace_from_markers([marker]))
    article.quality.source_trail = source_trail_from_trace(article.quality.trace)
    extend_unique(article.quality.warnings, list(warnings or []))
    return article


class BrowserWorkflowClient(ProviderClient):
    name = "browser_workflow"
    article_source_name: str | None = None
    profile: ProviderBrowserProfile | None = None

    def __init__(self, transport, env: Mapping[str, str]) -> None:
        self.transport = transport
        self.env = dict(env)
        self.user_agent = build_user_agent(env)

    def probe_status(self):
        return probe_runtime_status(self.env, provider=self.name)

    def fetch_metadata(self, query: Mapping[str, str | None]) -> ProviderMetadata:
        raise ProviderFailure(
            "not_supported",
            f"{self.name} official metadata retrieval is not implemented; routing relies on Crossref metadata.",
        )

    def article_source(self) -> str:
        if self.article_source_name:
            return self.article_source_name
        profile = self.profile
        if profile is not None and profile.article_source_name:
            return profile.article_source_name
        return self.name

    def require_profile(self) -> ProviderBrowserProfile:
        profile = self.profile
        if profile is None:
            raise ProviderFailure(
                "not_supported",
                f"{self.name} must declare a browser workflow profile.",
            )
        return profile

    def provider_label(self) -> str:
        profile = self.profile
        return profile.label if profile is not None else ("PNAS" if self.name == "pnas" else self.name.title())

    def allow_pdf_fallback_after_html_failure(
        self,
        *,
        html_failure_reason: str | None,
        html_failure_message: str | None,
    ) -> bool:
        return True

    def _recover_pdf_payload_from_abstract_only_html(
        self,
        doi: str,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
    ) -> RawFulltextPayload:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            raise ProviderFailure("not_supported", f"{self.name} PDF fallback requires a DOI.")
        content = raw_payload.content
        if content is None or normalize_text(content.route_kind).lower() != "html":
            raise ProviderFailure("not_supported", f"{self.name} PDF fallback recovery requires provider-owned HTML content.")

        html_failure_reason = "abstract_only"
        html_failure_message = f"{self.name} HTML route only exposed abstract-level content after markdown extraction."
        recovery_warning = (
            f"{self.name} HTML route only exposed abstract-level content after markdown extraction; attempting PDF fallback."
        )
        runtime = load_runtime_config(self.env, provider=self.name, doi=normalized_doi)
        ensure_runtime_ready(runtime)
        return fetch_seeded_browser_pdf_payload(
            provider=self.name,
            runtime=runtime,
            pdf_candidates=self.pdf_candidates(normalized_doi, metadata),
            html_candidates=self.html_candidates(normalized_doi, metadata),
            landing_page_url=str(metadata.get("landing_page_url") or raw_payload.source_url or "") or None,
            user_agent=self.user_agent,
            browser_context_seed=dict(content.browser_context_seed or {}),
            html_failure_reason=html_failure_reason,
            html_failure_message=html_failure_message,
            warnings=[*raw_payload.warnings, recovery_warning],
            success_source_trail=[
                f"fulltext:{self.name}_html_ok",
                f"fulltext:{self.name}_abstract_only",
                f"fulltext:{self.name}_pdf_fallback_ok",
            ],
        )

    def html_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        profile = self.require_profile()
        landing_page_url = str(metadata.get("landing_page_url") or "") or None
        return build_browser_workflow_html_candidates(
            doi,
            landing_page_url,
            hosts=profile.hosts,
            base_hosts=profile.base_hosts,
            path_templates=profile.html_path_templates,
        )

    def pdf_candidates(self, doi: str, metadata: ProviderMetadata) -> list[str]:
        profile = self.require_profile()
        crossref_pdf_url = extract_pdf_url_from_crossref(metadata)
        return build_browser_workflow_pdf_candidates(
            doi,
            crossref_pdf_url,
            hosts=profile.hosts,
            base_hosts=profile.base_hosts,
            path_templates=profile.pdf_path_templates,
            crossref_pdf_position=profile.crossref_pdf_position,
            base_seed_url=crossref_pdf_url if profile.crossref_pdf_position == 0 else None,
        )

    def extract_markdown(
        self,
        html_text: str,
        final_url: str,
        *,
        metadata: ProviderMetadata,
    ) -> tuple[str, dict[str, Any]]:
        profile = self.require_profile()
        return profile.extract_markdown(html_text, final_url, metadata=metadata)

    def fetch_raw_fulltext(self, doi: str, metadata: ProviderMetadata) -> RawFulltextPayload:
        bootstrap = bootstrap_browser_workflow(self, doi, metadata)
        if bootstrap.html_payload is not None:
            return bootstrap.html_payload

        if not self.allow_pdf_fallback_after_html_failure(
            html_failure_reason=bootstrap.html_failure_reason,
            html_failure_message=bootstrap.html_failure_message,
        ):
            reason = bootstrap.html_failure_message or f"{self.name} HTML route failed."
            raise ProviderFailure(
                "no_result",
                (
                    f"{self.name} HTML route was not usable ({bootstrap.html_failure_reason or 'html_failed'}); "
                    f"PDF fallback is disabled. {reason}"
                ),
                warnings=[f"{self.name} HTML route was not usable; skipping PDF fallback."],
                source_trail=[f"fulltext:{self.name}_html_fail"],
            )

        initial_warning = (
            f"{self.name} HTML route was not usable "
            f"({bootstrap.html_failure_reason or 'html_failed'}); attempting PDF fallback."
        )

        def run_pdf_fallback(_state) -> RawFulltextPayload:
            try:
                return fetch_seeded_browser_pdf_payload(
                    provider=self.name,
                    runtime=bootstrap.runtime,
                    pdf_candidates=bootstrap.pdf_candidates,
                    html_candidates=bootstrap.html_candidates,
                    landing_page_url=bootstrap.landing_page_url,
                    user_agent=self.user_agent,
                    browser_context_seed=bootstrap.browser_context_seed,
                    html_failure_reason=bootstrap.html_failure_reason,
                    html_failure_message=bootstrap.html_failure_message,
                    warnings=[],
                    success_source_trail=[],
                )
            except PdfFallbackFailure as exc:
                reason = bootstrap.html_failure_message or f"{self.name} HTML route failed."
                raise ProviderFailure(
                    "no_result",
                    (
                        f"{self.name} full text could not be retrieved via HTML or PDF fallback. "
                        f"HTML failure: {reason} PDF failure: {exc.message}"
                    ),
                ) from exc

        return run_provider_waterfall(
            [
                ProviderWaterfallStep(
                    label="pdf",
                    run=run_pdf_fallback,
                    success_markers=(f"fulltext:{self.name}_pdf_fallback_ok",),
                )
            ],
            initial_warnings=[*bootstrap.warnings, initial_warning],
            initial_source_trail=[f"fulltext:{self.name}_html_fail"],
        )

    def maybe_recover_fetch_result_payload(
        self,
        doi: str,
        metadata: Mapping[str, Any],
        prepared: PreparedFetchResultPayload,
        *,
        asset_profile: AssetProfile = "none",
    ) -> PreparedFetchResultPayload:
        raw_payload = prepared.raw_payload
        content = raw_payload.content
        if content is None or normalize_text(content.route_kind).lower() != "html":
            return prepared

        provisional_article = self.to_article_model(metadata, raw_payload)
        prepared.provisional_article = provisional_article
        if provisional_article.quality.content_kind != "abstract_only":
            return prepared

        if not self.allow_pdf_fallback_after_html_failure(
            html_failure_reason="abstract_only",
            html_failure_message=f"{self.name} HTML route only exposed abstract-level content after markdown extraction.",
        ):
            return prepared

        try:
            recovered_payload = self._recover_pdf_payload_from_abstract_only_html(doi, metadata, raw_payload)
        except (ProviderFailure, PdfFallbackFailure):
            provider_label = self.provider_label()
            prepared.finalize_warnings.append(
                (
                    f"{provider_label} HTML route only exposed abstract-level content after markdown extraction, "
                    "and PDF fallback did not return usable full text; returning abstract-only content."
                )
            )
            return prepared

        return PreparedFetchResultPayload(raw_payload=recovered_payload)

    def should_download_related_assets_for_result(
        self,
        raw_payload: RawFulltextPayload,
        *,
        provisional_article=None,
    ) -> bool:
        return provisional_article is None or provisional_article.quality.content_kind == "fulltext"

    def finalize_fetch_result_article(
        self,
        article,
        *,
        raw_payload: RawFulltextPayload,
        provisional_article=None,
        finalize_warnings: list[str] | None = None,
    ):
        if article.quality.content_kind != "abstract_only":
            return article
        return _finalize_abstract_only_provider_article(
            self.name,
            article,
            warnings=list(finalize_warnings or []),
        )

    def download_related_assets(
        self,
        doi: str,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        output_dir,
        *,
        asset_profile: AssetProfile = "all",
    ) -> dict[str, list[dict[str, Any]]]:
        if output_dir is None or asset_profile == "none":
            return empty_asset_results()
        content = raw_payload.content
        if normalize_text(content.route_kind if content is not None else "").lower() != "html":
            return empty_asset_results()

        html_text = decode_html(raw_payload.body)
        try:
            body_asset_html, supplementary_asset_html = extract_browser_workflow_asset_html_scopes(
                html_text,
                raw_payload.source_url,
                self.name,
            )
        except SciencePnasHtmlFailure:
            return empty_asset_results()
        article_assets = extract_scoped_html_assets(
            body_asset_html,
            raw_payload.source_url,
            asset_profile=asset_profile,
            supplementary_html_text=supplementary_asset_html,
        )
        if not article_assets:
            return empty_asset_results()
        body_assets, supplementary_assets = split_body_and_supplementary_assets(article_assets)

        normalized_doi = normalize_doi(str(metadata.get("doi") or doi or ""))
        if not normalized_doi:
            return empty_asset_results()

        runtime = load_runtime_config(self.env, provider=self.name, doi=normalized_doi)
        ensure_runtime_ready(runtime)
        browser_context_seed = merge_browser_context_seeds(content.browser_context_seed if content is not None else None)

        article_id = (
            normalized_doi
            or normalize_text(str(metadata.get("title") or ""))
            or raw_payload.source_url
        )

        def seed_urls_for(current_seed: Mapping[str, Any]) -> list[str]:
            return [
                normalized
                for normalized in [
                    raw_payload.source_url,
                    normalize_text(str(current_seed.get("browser_final_url") or "")),
                ]
                if normalized
            ]

        def asset_recovery_urls(image_url: str, asset: Mapping[str, Any]) -> list[str]:
            seen: set[str] = set()
            ordered: list[str] = []
            for candidate in [
                image_url,
                normalize_text(str(asset.get("figure_page_url") or "")),
            ]:
                normalized = normalize_text(candidate)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
            return ordered

        def supplementary_recovery_urls(file_url: str, asset: Mapping[str, Any]) -> list[str]:
            seen: set[str] = set()
            ordered: list[str] = []
            for candidate in [
                file_url,
                raw_payload.source_url,
                normalize_text(str(asset.get("source_url") or "")),
                normalize_text(str(asset.get("download_url") or "")),
            ]:
                normalized = normalize_text(candidate)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
            return ordered

        def asset_challenge_recovery_for(
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None]:
            def recover(image_url: str, asset: Mapping[str, Any], failure: Mapping[str, Any]) -> Mapping[str, Any]:
                attempts: list[dict[str, Any]] = []
                for recovery_url in asset_recovery_urls(image_url, asset):
                    try:
                        html_result = fetch_html_with_flaresolverr(
                            [recovery_url],
                            publisher=self.name,
                            config=runtime,
                            return_image_payload=True,
                        )
                    except FlareSolverrFailure as exc:
                        if exc.browser_context_seed:
                            with attempt_seed_lock:
                                attempt_seed.update(
                                    merge_browser_context_seeds(attempt_seed, exc.browser_context_seed)
                                )
                        attempts.append(
                            _compact_failure_diagnostic(
                                {
                                    "url": recovery_url,
                                    "status": "failed",
                                    "reason": "challenge_recovery_failed",
                                    "message": exc.message,
                                }
                            )
                        )
                        continue
                    with attempt_seed_lock:
                        attempt_seed.update(
                            merge_browser_context_seeds(attempt_seed, html_result.browser_context_seed)
                        )
                    image_payload = _flaresolverr_image_document_payload(html_result)
                    recovery_reason = (
                        ""
                        if image_payload is not None
                        else _flaresolverr_image_payload_failure_reason(html_result)
                    )
                    return _compact_failure_diagnostic(
                        {
                            "status": "ok" if image_payload is not None else "failed",
                            "url": recovery_url,
                            "final_url": html_result.final_url,
                            "response_status": html_result.response_status,
                            "content_type": html_result.response_headers.get("content-type"),
                            "title_snippet": (html_result.title or "")[:160],
                            "attempts": attempts,
                            "reason": recovery_reason,
                            "image_payload": image_payload,
                        }
                    )
                return _compact_failure_diagnostic(
                    {
                        "status": "failed",
                        "reason": normalize_text(str(failure.get("reason") or "")) or "challenge_recovery_failed",
                        "attempts": attempts,
                    }
                )

            return recover

        def supplementary_challenge_recovery_for(
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None]:
            def recover(file_url: str, asset: Mapping[str, Any], failure: Mapping[str, Any]) -> Mapping[str, Any]:
                attempts: list[dict[str, Any]] = []
                for recovery_url in supplementary_recovery_urls(file_url, asset):
                    try:
                        html_result = fetch_html_with_flaresolverr(
                            [recovery_url],
                            publisher=self.name,
                            config=runtime,
                        )
                    except FlareSolverrFailure as exc:
                        if exc.browser_context_seed:
                            with attempt_seed_lock:
                                attempt_seed.update(
                                    merge_browser_context_seeds(attempt_seed, exc.browser_context_seed)
                                )
                        attempts.append(
                            _compact_failure_diagnostic(
                                {
                                    "url": recovery_url,
                                    "status": "failed",
                                    "reason": "challenge_recovery_failed",
                                    "message": exc.message,
                                }
                            )
                        )
                        continue
                    with attempt_seed_lock:
                        attempt_seed.update(
                            merge_browser_context_seeds(attempt_seed, html_result.browser_context_seed)
                        )
                    return _compact_failure_diagnostic(
                        {
                            "status": "ok",
                            "url": recovery_url,
                            "final_url": html_result.final_url,
                            "response_status": html_result.response_status,
                            "content_type": html_result.response_headers.get("content-type"),
                            "title_snippet": (html_result.title or "")[:160],
                            "attempts": attempts,
                        }
                    )
                return _compact_failure_diagnostic(
                    {
                        "status": "failed",
                        "reason": normalize_text(str(failure.get("reason") or "")) or "challenge_recovery_failed",
                        "attempts": attempts,
                    }
                )

            return recover

        def image_document_fetcher_for(
            current_seed: Mapping[str, Any],
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[[str, Mapping[str, Any]], dict[str, Any] | None] | None:
            if not body_assets:
                return None
            profile = self.profile
            if profile is None or not profile.shared_playwright_image_fetcher:
                return None
            fetcher = _build_shared_playwright_image_fetcher(
                browser_context_seed_getter=lambda: attempt_seed,
                seed_urls_getter=lambda: seed_urls_for(attempt_seed),
                browser_user_agent=current_seed.get("browser_user_agent") or self.user_agent,
                headless=runtime.headless,
                challenge_recovery=asset_challenge_recovery_for(attempt_seed, attempt_seed_lock),
            )
            return _MemoizedImageDocumentFetcher(fetcher)

        def file_document_fetcher_for(
            current_seed: Mapping[str, Any],
            attempt_seed: dict[str, Any],
            attempt_seed_lock: threading.Lock,
        ) -> Callable[[str, Mapping[str, Any]], dict[str, Any] | None] | None:
            if not supplementary_assets:
                return None
            profile = self.profile
            if profile is None or not profile.shared_playwright_image_fetcher:
                return None
            return _build_shared_playwright_file_fetcher(
                browser_context_seed_getter=lambda: attempt_seed,
                seed_urls_getter=lambda: seed_urls_for(attempt_seed),
                browser_user_agent=current_seed.get("browser_user_agent") or self.user_agent,
                headless=runtime.headless,
                challenge_recovery=supplementary_challenge_recovery_for(attempt_seed, attempt_seed_lock),
            )

        def run_download_attempt(current_seed: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
            attempt_seed = merge_browser_context_seeds(current_seed)
            attempt_seed_lock = threading.Lock()

            def raw_figure_page_fetcher(figure_page_url: str) -> tuple[str, str] | None:
                try:
                    html_result = fetch_html_with_flaresolverr(
                        [figure_page_url],
                        publisher=self.name,
                        config=runtime,
                    )
                except FlareSolverrFailure:
                    return None
                with attempt_seed_lock:
                    attempt_seed.update(
                        merge_browser_context_seeds(attempt_seed, html_result.browser_context_seed)
                    )
                return html_result.html, html_result.final_url

            figure_page_fetcher = _MemoizedFigurePageFetcher(raw_figure_page_fetcher)
            image_document_fetcher = image_document_fetcher_for(attempt_seed, attempt_seed, attempt_seed_lock)
            file_document_fetcher = file_document_fetcher_for(attempt_seed, attempt_seed, attempt_seed_lock)
            try:
                body_result = download_figure_assets_with_image_document_fetcher(
                    self.transport,
                    article_id=article_id,
                    assets=body_assets,
                    output_dir=output_dir,
                    user_agent=self.user_agent,
                    asset_profile=asset_profile,
                    figure_page_fetcher=figure_page_fetcher,
                    candidate_builder=_browser_workflow_image_download_candidates,
                    image_document_fetcher=image_document_fetcher,
                )
                supplementary_result = download_supplementary_assets(
                    self.transport,
                    article_id=article_id,
                    assets=supplementary_assets,
                    output_dir=output_dir,
                    user_agent=self.user_agent,
                    asset_profile=asset_profile,
                    browser_context_seed=attempt_seed,
                    seed_urls=seed_urls_for(attempt_seed),
                    file_document_fetcher=file_document_fetcher,
                )
                return {
                    "assets": [
                        *list(body_result.get("assets") or []),
                        *list(supplementary_result.get("assets") or []),
                    ],
                    "asset_failures": [
                        *list(body_result.get("asset_failures") or []),
                        *list(supplementary_result.get("asset_failures") or []),
                    ],
                }
            finally:
                for fetcher in (image_document_fetcher, file_document_fetcher):
                    close_fetcher = getattr(fetcher, "close", None)
                    if callable(close_fetcher):
                        close_fetcher()

        initial_result = run_download_attempt(browser_context_seed)
        if not initial_result.get("asset_failures"):
            return initial_result

        refreshed_seed = warm_browser_context_with_flaresolverr(
            seed_urls_for(browser_context_seed),
            publisher=self.name,
            config=runtime,
            browser_context_seed=browser_context_seed,
        )
        retry_result = run_download_attempt(refreshed_seed)
        return _merge_download_attempt_results(initial_result, retry_result)

    def to_article_model(
        self,
        metadata: ProviderMetadata,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ):
        profile = self.require_profile()
        return browser_workflow_article_from_payload(
            self,
            merge_provider_owned_authors(
                metadata,
                raw_payload,
                fallback_extractor=profile.fallback_author_extractor,
            ),
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )

    def describe_artifacts(
        self,
        raw_payload: RawFulltextPayload,
        *,
        downloaded_assets: list[Mapping[str, Any]] | None = None,
        asset_failures: list[Mapping[str, Any]] | None = None,
    ) -> ProviderArtifacts:
        artifacts = super().describe_artifacts(
            raw_payload,
            downloaded_assets=downloaded_assets,
            asset_failures=asset_failures,
        )
        content = raw_payload.content
        if normalize_text(content.route_kind if content is not None else "").lower() != "pdf_fallback":
            return artifacts
        provider_label = self.provider_label()
        return ProviderArtifacts(
            assets=list(artifacts.assets),
            asset_failures=list(artifacts.asset_failures),
            allow_related_assets=False,
            text_only=True,
            skip_warning=(
                f"{provider_label} PDF fallback currently returns text-only full text; "
                "figure and supplementary asset downloads are not implemented yet."
            ),
            skip_trace=trace_from_markers([f"download:{self.name}_assets_skipped_text_only"]),
        )
