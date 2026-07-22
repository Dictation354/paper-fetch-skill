"""Supplementary file document fetchers for provider browser workflows."""

from __future__ import annotations

from typing import Any
from collections.abc import Callable, Mapping

from ....extraction.html.assets import supplementary_response_block_reason
from ....extraction.html.shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
)
from ....runtime import RuntimeContext
from ...browser_runtime.types import BrowserRuntimeConfig
from ....utils import normalize_text
from .context import (
    _BaseBrowserDocumentFetcher,
    _ThreadLocalSharedDocumentFetcher,
    _browser_response_headers,
    _browser_response_status,
)


class _SharedBrowserFileDocumentFetcher(_BaseBrowserDocumentFetcher):
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        runtime_context: RuntimeContext | None = None,
        use_runtime_shared_browser: bool = True,
        binary_path: str | None = None,
        cdp_endpoint: str | None = None,
        profile_dir: Any = None,
        user_data_dir: Any = None,
        browser_config: BrowserRuntimeConfig | None = None,
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
            browser_config=browser_config,
        )

    def __call__(
        self, file_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        normalized_url = normalize_text(file_url)
        if not normalized_url:
            return None
        if self._ensure_context(normalized_url) is None:
            return None

        self._sync_context_cookies()
        self._warm_seed_urls(force=False)
        for attempt in range(3):
            result = self._fetch_with_context_request(normalized_url, asset)
            if result is not None:
                return result
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

    def _fetch_with_context_request(
        self,
        file_url: str,
        asset: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        if self._context is None:
            return None
        request_headers = {"Accept": "*/*"}
        referer_url = normalize_text(str(asset.get("referer_url") or ""))
        if referer_url:
            request_headers["Referer"] = referer_url
        try:
            response = self._context.request.get(
                file_url,
                headers=request_headers,
                timeout=60000,
            )
        except Exception as exc:
            self._record_failure(
                file_url,
                reason=normalize_text(str(exc)) or exc.__class__.__name__,
            )
            return None

        headers = _browser_response_headers(response)
        content_type = headers.get("content-type", "")
        final_url = normalize_text(getattr(response, "url", "") or "") or file_url
        status = _browser_response_status(response)
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


class _ThreadLocalSharedBrowserFileDocumentFetcher(_ThreadLocalSharedDocumentFetcher):
    def __init__(
        self,
        *,
        browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
        seed_urls_getter: Callable[[], list[str]],
        browser_user_agent: str | None = None,
        headless: bool = True,
        runtime_context: RuntimeContext | None = None,
        use_runtime_shared_browser: bool = True,
        binary_path: str | None = None,
        cdp_endpoint: str | None = None,
        profile_dir: Any = None,
        user_data_dir: Any = None,
        browser_config: BrowserRuntimeConfig | None = None,
    ) -> None:
        requires_caller_thread = (
            runtime_context is not None and use_runtime_shared_browser
        )
        super().__init__(
            log_event="browser_workflow_file_fetcher_thread_created",
            requires_caller_thread=requires_caller_thread,
            close_after_call=not requires_caller_thread,
            fetcher_factory=lambda: _SharedBrowserFileDocumentFetcher(
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
                browser_config=browser_config,
            ),
        )


def _build_shared_browser_file_fetcher(
    *,
    browser_context_seed_getter: Callable[[], Mapping[str, Any] | None],
    seed_urls_getter: Callable[[], list[str]],
    browser_user_agent: str | None = None,
    headless: bool = True,
    runtime_context: RuntimeContext | None = None,
    use_runtime_shared_browser: bool = True,
    binary_path: str | None = None,
    cdp_endpoint: str | None = None,
    profile_dir: Any = None,
    user_data_dir: Any = None,
    thread_local: bool = False,
    browser_config: BrowserRuntimeConfig | None = None,
) -> _ThreadLocalSharedBrowserFileDocumentFetcher | _SharedBrowserFileDocumentFetcher:
    fetcher_cls: (
        type[_ThreadLocalSharedBrowserFileDocumentFetcher]
        | type[_SharedBrowserFileDocumentFetcher]
    )
    fetcher_cls = (
        _ThreadLocalSharedBrowserFileDocumentFetcher
        if thread_local
        else _SharedBrowserFileDocumentFetcher
    )
    return fetcher_cls(
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
        browser_config=browser_config,
    )
