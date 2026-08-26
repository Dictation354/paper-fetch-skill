"""Image document fetchers for provider browser workflows."""

from __future__ import annotations

import time
from typing import Any
from collections.abc import Callable, Mapping

from ....extraction.html.shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
    image_magic_type as _image_magic_type,
)
from ....extraction.image_payloads import is_placeholder_image_url
from ....extraction.html.signals import (
    CLOUDFLARE_CHALLENGE_TITLE_TOKENS as _CLOUDFLARE_CHALLENGE_TITLE_TOKENS,
)
from ....quality.reason_codes import CLOUDFLARE_CHALLENGE
from ....reason_codes import BROWSER_STREAM_UNAVAILABLE
from ....runtime import RuntimeContext
from ....utils import normalize_text
from ...browser_runtime.types import BrowserFetchedHtml
from .context import (
    BrowserDocumentFetcherOptions,
    _BaseBrowserDocumentFetcher,
    _ThreadLocalSharedDocumentFetcher,
    _browser_response_headers,
    _browser_response_status,
)
from .diagnostics import _looks_like_cloudflare_challenge_title

_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS = 15000
_IMAGE_DOCUMENT_TOTAL_BUDGET_SECONDS = 30.0
_IMAGE_DOCUMENT_SEED_WARM_TIMEOUT_MS = 5000
_IMAGE_DOCUMENT_NAVIGATION_TIMEOUT_MS = 10000
_IMAGE_DOCUMENT_MAX_ATTEMPTS = 2


class _ImageFetchBudget:
    def __init__(self, seconds: float = _IMAGE_DOCUMENT_TOTAL_BUDGET_SECONDS) -> None:
        self._deadline = time.monotonic() + max(0.0, seconds)

    def remaining_seconds(self) -> float:
        return max(0.0, self._deadline - time.monotonic())

    def exhausted(self) -> bool:
        return self.remaining_seconds() <= 0

    def timeout_ms(self, requested_ms: int) -> int:
        remaining_ms = int(self.remaining_seconds() * 1000)
        if remaining_ms <= 0:
            return 0
        return max(1, min(requested_ms, remaining_ms))

    def loop_deadline(self, max_seconds: float) -> float:
        return time.monotonic() + min(max(0.0, max_seconds), self.remaining_seconds())


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


def _looks_like_placeholder_image_url(source_url: str | None) -> bool:
    return is_placeholder_image_url(source_url)


def _browser_image_document_payload(
    result: BrowserFetchedHtml,
) -> dict[str, Any] | None:
    return _payload_from_browser_image_payload(
        result.image_payload,
        fallback_url=result.final_url or result.source_url,
    )


def _payload_from_browser_image_payload(
    payload: Mapping[str, Any] | None,
    *,
    fallback_url: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    if payload.get("streamOnly") is not True:
        return None
    if "bodyB64" in payload or "body" in payload:
        return None
    content_type = normalize_text(str(payload.get("contentType") or "")) or "image/png"
    final_url = normalize_text(str(payload.get("url") or "")) or fallback_url
    if _looks_like_placeholder_image_url(final_url):
        return None
    if not final_url.lower().startswith(("http://", "https://")):
        return None
    if not content_type.lower().startswith("image/"):
        return None
    try:
        width = int(payload.get("width") or 0)
        height = int(payload.get("height") or 0)
    except (TypeError, ValueError):
        width = height = 0
    try:
        status = int(payload.get("status") or 200)
    except (TypeError, ValueError):
        return None
    if not 200 <= status < 400:
        return None
    return {
        "status_code": status,
        "headers": {"content-type": content_type},
        "url": final_url,
        "_paper_fetch_browser_stream_url": final_url,
        "_paper_fetch_browser_cookies": [],
        "dimensions": {"width": width, "height": height},
    }


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


class _SharedBrowserImageDocumentFetcher(_BaseBrowserDocumentFetcher):
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        min_width: int = 80,
        min_height: int = 80,
        runtime_context: RuntimeContext | None = None,
        use_runtime_shared_browser: bool = True,
        binary_path: str | None = None,
        cdp_endpoint: str | None = None,
        profile_dir: Any = None,
        user_data_dir: Any = None,
        browser_options: BrowserDocumentFetcherOptions | None = None,
    ) -> None:
        super().__init__(
            browser_context_seed_getter=browser_context_seed_getter,
            seed_urls_getter=seed_urls_getter,
            browser_user_agent=browser_user_agent,
            headless=headless,
            runtime_context=runtime_context,
            use_runtime_shared_browser=use_runtime_shared_browser,
            binary_path=binary_path,
            cdp_endpoint=cdp_endpoint,
            profile_dir=profile_dir,
            user_data_dir=user_data_dir,
            browser_options=browser_options,
        )
        self._min_width = min_width
        self._min_height = min_height
        self._active_image_fetch_budget: _ImageFetchBudget | None = None

    def __call__(
        self, image_url: str, _asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        normalized_url = normalize_text(image_url)
        if not normalized_url:
            return None
        if not self._browser_target_is_allowed(normalized_url):
            return None
        page = self._ensure_page(normalized_url)
        if page is None:
            return None

        budget = _ImageFetchBudget()
        self._sync_context_cookies()
        self._warm_seed_urls(
            force=False,
            timeout_ms=budget.timeout_ms(_IMAGE_DOCUMENT_SEED_WARM_TIMEOUT_MS),
            max_urls=1,
        )
        previous_budget: _ImageFetchBudget | None = self._active_image_fetch_budget
        self._active_image_fetch_budget = budget
        try:
            for attempt in range(_IMAGE_DOCUMENT_MAX_ATTEMPTS):
                if budget.exhausted():
                    self._record_failure(
                        normalized_url, reason="image_fetch_budget_exhausted"
                    )
                    return None
                result = self._fetch_with_page(normalized_url)
                if result is not None:
                    return result
                if attempt == 0:
                    self._sync_context_cookies()
                    self._warm_seed_urls(
                        force=True,
                        timeout_ms=budget.timeout_ms(
                            _IMAGE_DOCUMENT_SEED_WARM_TIMEOUT_MS
                        ),
                        max_urls=1,
                    )
                    continue
                break
            return None
        finally:
            self._active_image_fetch_budget = previous_budget

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
            CLOUDFLARE_CHALLENGE
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

    def _active_budget(self) -> _ImageFetchBudget:
        budget = self._active_image_fetch_budget
        return budget if budget is not None else _ImageFetchBudget()

    def _fetch_with_page(self, image_url: str) -> dict[str, Any] | None:
        budget = self._active_budget()
        previous_budget: _ImageFetchBudget | None = self._active_image_fetch_budget
        self._active_image_fetch_budget = budget
        page = self._page
        try:
            if page is None:
                return None
            warmed_article_payload = self._payload_from_warmed_article_image(
                page, image_url, budget=budget
            )
            if warmed_article_payload is not None:
                return warmed_article_payload
            return None
        finally:
            self._active_image_fetch_budget = previous_budget

    def _payload_from_warmed_article_image(
        self,
        page: Any,
        image_url: str,
        *,
        budget: _ImageFetchBudget | None = None,
    ) -> dict[str, Any] | None:
        del page
        budget = budget or self._active_budget()
        image_src = normalize_text(str(image_url or ""))
        if not image_src:
            return None
        if self._network_guard is None and not self._browser_target_is_allowed(
            image_src
        ):
            return None
        if budget.exhausted():
            return None
        return self._stream_descriptor(
            image_src,
            headers={"content-type": "image/*"},
            previous_url=image_src,
        )

    def _payload_from_context_request(
        self, image_url: str, *, budget: _ImageFetchBudget | None = None
    ) -> dict[str, Any] | None:
        budget = budget or self._active_budget()
        if self._context is None:
            return None
        if self._network_guard is None and not self._browser_target_is_allowed(
            image_url
        ):
            return None
        if budget.timeout_ms(_IMAGE_DOCUMENT_NAVIGATION_TIMEOUT_MS) <= 0:
            return None
        return self._stream_descriptor(
            image_url,
            headers={"content-type": "image/*"},
            previous_url=image_url,
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
        headers = _browser_response_headers(response)
        content_type = headers.get("content-type", "")
        final_url = normalize_text(getattr(response, "url", "") or "") or fallback_url
        if not self._validate_browser_url(
            final_url,
            previous_url=attempted_url,
            resolve_dns=True,
        ):
            self._record_failure(attempted_url, reason="unsafe_browser_final_url")
            return None
        status = _browser_response_status(response)
        if _looks_like_placeholder_image_url(final_url):
            self._record_failure(
                attempted_url,
                status=status,
                content_type=content_type,
                final_url=final_url,
                reason="placeholder_image_response",
            )
            return None
        return self._stream_descriptor(
            final_url,
            status=int(status or 200),
            headers=headers,
            previous_url=attempted_url,
        )

    def _wait_for_primary_image(
        self,
        page: Any,
        image_url: str,
        *,
        budget: _ImageFetchBudget | None = None,
    ) -> dict[str, Any] | None:
        deadline = (
            budget.loop_deadline(15.0)
            if budget is not None
            else time.monotonic() + 15.0
        )
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
                    reason=CLOUDFLARE_CHALLENGE,
                )
                return None
            try:
                timeout_ms = 500 if budget is None else min(500, budget.timeout_ms(500))
                page.wait_for_timeout(timeout_ms)
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
        budget: _ImageFetchBudget | None = None,
    ) -> dict[str, Any] | None:
        image_src = normalize_text(str(image_url or ""))
        if not image_src:
            return None
        if self._network_guard is None and not self._browser_target_is_allowed(
            image_src
        ):
            return None
        if not self._validate_browser_url(image_src, resolve_dns=True):
            return None
        budget = budget or self._active_budget()
        timeout_ms = (
            budget.timeout_ms(_IMAGE_DOCUMENT_FETCH_TIMEOUT_MS)
            if budget is not None
            else _IMAGE_DOCUMENT_FETCH_TIMEOUT_MS
        )
        if timeout_ms <= 0:
            return None
        del page
        return self._stream_descriptor(
            image_src,
            headers={"content-type": "image/*"},
            dimensions={
                "width": int((dimensions or {}).get("width") or 0),
                "height": int((dimensions or {}).get("height") or 0),
            },
            previous_url=image_src,
        )

    def _payload_from_page_fetch(
        self,
        page: Any,
        image_info: Mapping[str, Any],
        *,
        budget: _ImageFetchBudget | None = None,
    ) -> dict[str, Any] | None:
        budget = budget or self._active_budget()
        payload = self._payload_from_page_fetch_url(
            page,
            normalize_text(str(image_info.get("src") or "")),
            dimensions=image_info,
            budget=budget,
        )
        if payload is not None:
            return payload
        return self._payload_from_loaded_image(page, image_info)

    def _payload_from_loaded_image(
        self, page: Any, image_info: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        del page
        image_src = normalize_text(str(image_info.get("src") or ""))
        if not image_src:
            return None
        if not image_src.lower().startswith(("http://", "https://")):
            self._record_failure(
                image_src,
                reason=BROWSER_STREAM_UNAVAILABLE,
            )
            return None
        return self._stream_descriptor(
            image_src,
            headers={"content-type": "image/*"},
            dimensions={
                "width": int(image_info.get("width") or 0),
                "height": int(image_info.get("height") or 0),
            },
            previous_url=image_src,
        )


class _ThreadLocalSharedBrowserImageDocumentFetcher(_ThreadLocalSharedDocumentFetcher):
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        min_width: int = 80,
        min_height: int = 80,
        runtime_context: RuntimeContext | None = None,
        use_runtime_shared_browser: bool = True,
        binary_path: str | None = None,
        cdp_endpoint: str | None = None,
        profile_dir: Any = None,
        user_data_dir: Any = None,
        browser_options: BrowserDocumentFetcherOptions | None = None,
    ) -> None:
        requires_caller_thread = (
            runtime_context is not None and use_runtime_shared_browser
        )
        super().__init__(
            log_event="browser_workflow_image_fetcher_thread_created",
            requires_caller_thread=requires_caller_thread,
            close_after_call=not requires_caller_thread,
            fetcher_factory=lambda: _SharedBrowserImageDocumentFetcher(
                browser_context_seed_getter=browser_context_seed_getter,
                seed_urls_getter=seed_urls_getter,
                browser_user_agent=browser_user_agent,
                headless=headless,
                min_width=min_width,
                min_height=min_height,
                runtime_context=runtime_context,
                use_runtime_shared_browser=use_runtime_shared_browser,
                binary_path=binary_path,
                cdp_endpoint=cdp_endpoint,
                profile_dir=profile_dir,
                user_data_dir=user_data_dir,
                browser_options=browser_options,
            ),
        )


def _build_shared_browser_image_fetcher(
    *,
    browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
    seed_urls_getter: Callable[[], list[str]],
    browser_user_agent: str | None = None,
    headless: bool = True,
    min_width: int = 80,
    min_height: int = 80,
    runtime_context: RuntimeContext | None = None,
    use_runtime_shared_browser: bool = True,
    binary_path: str | None = None,
    cdp_endpoint: str | None = None,
    profile_dir: Any = None,
    user_data_dir: Any = None,
    browser_options: BrowserDocumentFetcherOptions | None = None,
) -> _ThreadLocalSharedBrowserImageDocumentFetcher:
    return _ThreadLocalSharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=browser_context_seed_getter,
        seed_urls_getter=seed_urls_getter,
        browser_user_agent=browser_user_agent,
        headless=headless,
        min_width=min_width,
        min_height=min_height,
        runtime_context=runtime_context,
        use_runtime_shared_browser=use_runtime_shared_browser,
        binary_path=binary_path,
        cdp_endpoint=cdp_endpoint,
        profile_dir=profile_dir,
        user_data_dir=user_data_dir,
        browser_options=browser_options,
    )


def fetch_image_document_with_browser(
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
    fetcher = _build_shared_browser_image_fetcher(
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
