"""Supplementary file document fetchers for provider browser workflows."""

from __future__ import annotations

from typing import Any
from collections.abc import Callable, Mapping

from ....extraction.html.shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
)
from ....runtime import RuntimeContext
from ....utils import normalize_text
from .context import (
    BrowserDocumentFetcherOptions,
    _BaseBrowserDocumentFetcher,
    _ThreadLocalSharedDocumentFetcher,
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
        return self._fetch_with_context_request(normalized_url, asset)

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
        content_type = normalize_text(str(asset.get("content_type") or ""))
        headers = {"content-type": content_type} if content_type else {}
        descriptor = self._stream_descriptor(
            file_url,
            headers=headers,
        )
        if descriptor is None:
            return None
        referer = normalize_text(
            str(asset.get("referer_url") or asset.get("source_page_url") or "")
        )
        direct_headers = {"Accept": "*/*"}
        if referer:
            direct_headers["Referer"] = referer
        descriptor["_paper_fetch_direct_headers"] = direct_headers
        return descriptor


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
        browser_options: BrowserDocumentFetcherOptions | None = None,
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
                browser_options=browser_options,
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
    browser_options: BrowserDocumentFetcherOptions | None = None,
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
        browser_options=browser_options,
    )
