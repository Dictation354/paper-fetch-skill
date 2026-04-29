"""Supplementary file document fetchers for provider browser workflows."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Mapping

from ...extraction.html.assets import supplementary_response_block_reason
from ...extraction.html.shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
)
from ...logging_utils import emit_structured_log
from ...runtime import RuntimeContext
from ...utils import normalize_text
from .context import _BasePlaywrightDocumentFetcher, _normalized_response_headers
from .diagnostics import _looks_like_cloudflare_challenge_failure

logger = logging.getLogger("paper_fetch.providers.browser_workflow")


class _SharedPlaywrightFileDocumentFetcher(_BasePlaywrightDocumentFetcher):
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
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

    def __call__(
        self, file_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
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
                and self._attempt_challenge_recovery(
                    normalized_url, asset, failure or {}
                )
            ):
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
            headers = _normalized_response_headers(
                getattr(response, "headers", {}) or {}
            )
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


class _ThreadLocalSharedPlaywrightFileDocumentFetcher:
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
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
        self._challenge_recovery = challenge_recovery
        self._runtime_context = runtime_context
        self._use_runtime_shared_browser = use_runtime_shared_browser
        self._thread_local = threading.local()
        self._lock = threading.Lock()
        self._fetchers: list[_SharedPlaywrightFileDocumentFetcher] = []

    def _get_fetcher(self) -> _SharedPlaywrightFileDocumentFetcher:
        fetcher = getattr(self._thread_local, "fetcher", None)
        if isinstance(fetcher, _SharedPlaywrightFileDocumentFetcher):
            return fetcher
        fetcher = _SharedPlaywrightFileDocumentFetcher(
            browser_context_seed_getter=self._browser_context_seed_getter,
            seed_urls_getter=self._seed_urls_getter,
            browser_user_agent=self._browser_user_agent,
            headless=self._headless,
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
            "browser_workflow_file_fetcher_thread_created",
            thread=threading.current_thread().name,
        )
        return fetcher

    def __call__(
        self, file_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        return self._get_fetcher()(file_url, asset)

    def failure_for(self, file_url: str) -> dict[str, Any] | None:
        fetcher = getattr(self._thread_local, "fetcher", None)
        if not isinstance(fetcher, _SharedPlaywrightFileDocumentFetcher):
            return None
        return fetcher.failure_for(file_url)

    def close(self) -> None:
        with self._lock:
            fetchers = list(self._fetchers)
            self._fetchers.clear()
        for fetcher in fetchers:
            fetcher.close()


def _build_shared_playwright_file_fetcher(
    *,
    browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
    seed_urls_getter: Callable[[], list[str]],
    browser_user_agent: str | None = None,
    headless: bool = True,
    challenge_recovery: Callable[
        [str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any] | None
    ]
    | None = None,
    runtime_context: RuntimeContext | None = None,
    use_runtime_shared_browser: bool = True,
    thread_local: bool = False,
) -> (
    _ThreadLocalSharedPlaywrightFileDocumentFetcher
    | _SharedPlaywrightFileDocumentFetcher
):
    fetcher_cls: (
        type[_ThreadLocalSharedPlaywrightFileDocumentFetcher]
        | type[_SharedPlaywrightFileDocumentFetcher]
    )
    fetcher_cls = (
        _ThreadLocalSharedPlaywrightFileDocumentFetcher
        if thread_local
        else _SharedPlaywrightFileDocumentFetcher
    )
    return fetcher_cls(
        browser_context_seed_getter=browser_context_seed_getter,
        seed_urls_getter=seed_urls_getter,
        browser_user_agent=browser_user_agent,
        headless=headless,
        challenge_recovery=challenge_recovery,
        runtime_context=runtime_context,
        use_runtime_shared_browser=use_runtime_shared_browser,
    )
