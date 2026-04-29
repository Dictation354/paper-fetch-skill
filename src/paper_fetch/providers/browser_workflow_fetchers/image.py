"""Image document fetchers for provider browser workflows."""

from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Any, Callable, Mapping

from ...extraction.html.shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
    image_magic_type as _image_magic_type,
)
from ...logging_utils import emit_structured_log
from ...runtime import RuntimeContext
from ...utils import normalize_text
from .._flaresolverr import FetchedPublisherHtml
from .context import _BasePlaywrightDocumentFetcher, _normalized_response_headers
from .diagnostics import (
    _CLOUDFLARE_CHALLENGE_TITLE_TOKENS,
    _compact_failure_diagnostic,
    _image_fetch_failure_reason,
    _looks_like_cloudflare_challenge_failure,
    _looks_like_cloudflare_challenge_title,
)
from .scripts import _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT

logger = logging.getLogger("paper_fetch.providers.browser_workflow")

_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS = 15000


def _decode_base64_bytes(payload: str | None) -> bytes | None:
    normalized = normalize_text(payload)
    if not normalized:
        return None
    try:
        return base64.b64decode(normalized, validate=True)
    except Exception:
        return None


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
    headers = (
        payload.get("headers") if isinstance(payload.get("headers"), Mapping) else {}
    )
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


def _flaresolverr_image_document_payload(
    result: FetchedPublisherHtml,
) -> dict[str, Any] | None:
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
    if body is None or not _looks_like_image_response_payload(
        content_type, body, final_url
    ):
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


class _SharedPlaywrightImageDocumentFetcher(_BasePlaywrightDocumentFetcher):
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        min_width: int = 80,
        min_height: int = 80,
        challenge_recovery: Callable[
            [str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None
        ]
        | None = None,
        runtime_context: RuntimeContext | None = None,
        use_runtime_shared_browser: bool = True,
    ) -> None:
        super().__init__(
            browser_context_seed_getter=browser_context_seed_getter,
            seed_urls_getter=seed_urls_getter,
            browser_user_agent=browser_user_agent,
            headless=headless,
            challenge_recovery=challenge_recovery,
            runtime_context=runtime_context,
            use_runtime_shared_browser=use_runtime_shared_browser,
        )
        self._min_width = min_width
        self._min_height = min_height
        self._recovered_payload_by_url: dict[str, dict[str, Any]] = {}

    def __call__(
        self, image_url: str, _asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
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
                and self._attempt_challenge_recovery(
                    normalized_url, _asset, failure or {}
                )
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
            or any(
                token in body_snippet.lower()
                for token in _CLOUDFLARE_CHALLENGE_TITLE_TOKENS
            )
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

    def _record_recovery_payload(
        self, image_url: str, recovery: Mapping[str, Any]
    ) -> None:
        recovered_payload = _normalized_recovered_image_payload(
            recovery.get("image_payload"), fallback_url=image_url
        )
        if recovered_payload is not None:
            self._recovered_payload_by_url[image_url] = recovered_payload

    def _recovery_diagnostic(self, recovery: Mapping[str, Any]) -> dict[str, Any]:
        diagnostic_recovery = {
            key: value for key, value in recovery.items() if key != "image_payload"
        }
        if normalize_text(
            str(diagnostic_recovery.get("status") or "")
        ).lower() != "ok" and not normalize_text(
            str(diagnostic_recovery.get("reason") or "")
        ):
            diagnostic_recovery["reason"] = "challenge_recovery_failed"
        return _compact_failure_diagnostic(diagnostic_recovery)

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
            navigation_response = page.goto(
                image_url, wait_until="domcontentloaded", timeout=60000
            )
        except Exception:
            navigation_response = None

        direct_payload = self._payload_from_navigation_response(
            navigation_response, fallback_url=image_url
        )
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
                headers={
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                },
                timeout=60000,
            )
        except Exception as exc:
            self._record_failure(
                image_url,
                reason=_image_fetch_failure_reason(error=str(exc)),
                canvas_error=normalize_text(str(exc)),
            )
            return None
        return self._payload_from_response_body(
            response, fallback_url=image_url, attempted_url=image_url
        )

    def _payload_from_navigation_response(
        self, response: Any, *, fallback_url: str
    ) -> dict[str, Any] | None:
        if response is None:
            return None
        return self._payload_from_response_body(
            response, fallback_url=fallback_url, attempted_url=fallback_url
        )

    def _payload_from_response_body(
        self, response: Any, *, fallback_url: str, attempted_url: str
    ) -> dict[str, Any] | None:
        try:
            headers = _normalized_response_headers(response.all_headers())
        except Exception:
            headers = _normalized_response_headers(
                getattr(response, "headers", {}) or {}
            )
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

    def _wait_for_primary_image(
        self, page: Any, image_url: str
    ) -> dict[str, Any] | None:
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
            if isinstance(
                image_info, Mapping
            ) and _looks_like_cloudflare_challenge_title(
                str(image_info.get("title") or "")
            ):
                self._record_failure(
                    image_url,
                    content_type=normalize_text(
                        str(image_info.get("contentType") or "")
                    ),
                    final_url=normalize_text(
                        str(getattr(page, "url", "") or image_url)
                    ),
                    title_snippet=normalize_text(str(image_info.get("title") or ""))[
                        :160
                    ],
                    reason="cloudflare_challenge",
                )
                return None
            try:
                page.wait_for_timeout(500)
            except Exception:
                break
        self._record_failure(
            image_url,
            content_type=normalize_text(
                str((last_info or {}).get("contentType") or "")
            ),
            final_url=normalize_text(str(getattr(page, "url", "") or image_url)),
            title_snippet=normalize_text(str((last_info or {}).get("title") or ""))[
                :160
            ],
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
        if body is None or not _looks_like_image_response_payload(
            content_type, body, final_url
        ):
            fallback_body = body
            if fallback_body is None:
                fallback_body = str(fetched.get("bodySnippet") or "").encode(
                    "utf-8", errors="replace"
                )
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

    def _payload_from_page_fetch(
        self, page: Any, image_info: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        payload = self._payload_from_page_fetch_url(
            page,
            normalize_text(str(image_info.get("src") or "")),
            dimensions=image_info,
        )
        if payload is not None:
            return payload
        return self._payload_from_loaded_image(page, image_info)

    def _payload_from_loaded_image(
        self, page: Any, image_info: Mapping[str, Any]
    ) -> dict[str, Any] | None:
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
        content_type = (
            normalize_text(str(rendered.get("contentType") or "")) or "image/png"
        )
        if (
            not rendered.get("ok")
            or body is None
            or not _looks_like_image_response_payload(content_type, body, final_url)
        ):
            previous = self.failure_for(image_src) or {}
            failure_values = {
                **previous,
                "final_url": final_url,
                "title_snippet": normalize_text(str(rendered.get("title") or ""))[:160],
                "content_type": content_type,
                "reason": normalize_text(str(rendered.get("reason") or ""))
                or "canvas_serialization_failed",
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
        challenge_recovery: Callable[
            [str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None
        ]
        | None = None,
        runtime_context: RuntimeContext | None = None,
        use_runtime_shared_browser: bool = True,
    ) -> None:
        self._browser_context_seed_getter = browser_context_seed_getter
        self._seed_urls_getter = seed_urls_getter
        self._browser_user_agent = browser_user_agent
        self._headless = headless
        self._min_width = min_width
        self._min_height = min_height
        self._challenge_recovery = challenge_recovery
        self._runtime_context = runtime_context
        self._use_runtime_shared_browser = use_runtime_shared_browser
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
            runtime_context=self._runtime_context,
            use_runtime_shared_browser=self._use_runtime_shared_browser,
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

    def __call__(
        self, image_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
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


def _build_shared_playwright_image_fetcher(
    *,
    browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
    seed_urls_getter: Callable[[], list[str]],
    browser_user_agent: str | None = None,
    headless: bool = True,
    min_width: int = 80,
    min_height: int = 80,
    challenge_recovery: Callable[
        [str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None
    ]
    | None = None,
    runtime_context: RuntimeContext | None = None,
    use_runtime_shared_browser: bool = True,
) -> _ThreadLocalSharedPlaywrightImageDocumentFetcher:
    return _ThreadLocalSharedPlaywrightImageDocumentFetcher(
        browser_context_seed_getter=browser_context_seed_getter,
        seed_urls_getter=seed_urls_getter,
        browser_user_agent=browser_user_agent,
        headless=headless,
        min_width=min_width,
        min_height=min_height,
        challenge_recovery=challenge_recovery,
        runtime_context=runtime_context,
        use_runtime_shared_browser=use_runtime_shared_browser,
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
                (
                    normalize_text(candidate)
                    for candidate in reversed(seed_urls or [])
                    if normalize_text(candidate)
                ),
                None,
            ),
        },
        seed_urls_getter=lambda: [
            normalize_text(url) for url in seed_urls or [] if normalize_text(url)
        ],
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
