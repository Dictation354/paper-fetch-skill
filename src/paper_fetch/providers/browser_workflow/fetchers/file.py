"""Supplementary file document fetchers for provider browser workflows."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit, urlunsplit

from typing import Any
from collections.abc import Callable, Mapping

from ....asset_budget import DEFAULT_ASSET_MAX_BYTES_PER_ASSET
from ....extraction.html.assets import supplementary_response_block_reason
from ....extraction.html.shared import (
    html_text_snippet as _html_text_snippet,
    html_title_snippet as _html_title_snippet,
)
from ....runtime import RuntimeContext
from ....utils import normalize_text
from .readiness import wait_for_atypon_body_dom_ready
from .context import (
    BrowserDocumentFetcherOptions,
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
        browser_options: BrowserDocumentFetcherOptions | None = None,
    ) -> None:
        super().__init__(
            browser_context_seed_getter=browser_context_seed_getter,
            seed_urls_getter=seed_urls_getter,
            browser_user_agent=browser_user_agent,
            headless=headless,
            runtime_context=runtime_context,
            use_runtime_shared_browser=use_runtime_shared_browser,
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
        if getattr(self._browser_config, "provider", None) == "wiley":
            return self._fetch_wiley_with_page_click(normalized_url, asset)
        self._warm_seed_urls(force=False)
        return self._fetch_with_context_request(normalized_url, asset)

    def _fetch_wiley_with_page_click(
        self, file_url: str, asset: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        page = self._page
        if page is None:
            self._record_failure(file_url, reason="wiley_supplement_page_unavailable")
            return None
        deadline = time.monotonic() + 60.0
        response = None
        download = None
        phase = "article_not_ready"

        def remaining_ms() -> int:
            remaining = deadline - time.monotonic()
            if self._runtime_context is not None:
                remaining = self._runtime_context.remaining_seconds(remaining)
            if remaining <= 0:
                raise TimeoutError("Wiley supplementary download deadline exceeded.")
            return max(1, int(remaining * 1000))

        def capture_response(candidate: Any) -> None:
            nonlocal response
            request = candidate.request
            while request is not None:
                if request.url == file_url:
                    if not 300 <= candidate.status < 400:
                        response = candidate
                    return
                request = request.redirected_from

        try:
            seed_url = str(self._current_seed().get("browser_final_url") or "")
            if not seed_url:
                seed_url = next(iter(self._seed_urls()), "")
            if seed_url and page.url != seed_url:
                page.goto(seed_url, wait_until="commit", timeout=remaining_ms())
            readiness = wait_for_atypon_body_dom_ready(
                page, "wiley", timeout_seconds=remaining_ms() / 1000.0
            )
            if not readiness.ready:
                body = page.content().encode()
                self._record_response_failure(
                    file_url,
                    status=None,
                    content_type="text/html",
                    final_url=page.url,
                    body=body,
                    reason=supplementary_response_block_reason("text/html", body)
                    or "wiley_supplement_article_not_ready",
                )
                return None
            phase = "panel_not_ready"
            supporting = page.locator("section.article-section__supporting")
            supporting.first.wait_for(state="attached", timeout=remaining_ms())
            parsed = urlsplit(file_url)
            relative_url = urlunsplit(
                ("", "", parsed.path, parsed.query, parsed.fragment)
            )
            selector = (
                f"a[href={json.dumps(file_url)}], a[href={json.dumps(relative_url)}]"
            )
            link = supporting.locator(selector).first
            phase = "link_missing"
            link.wait_for(state="attached", timeout=remaining_ms())
            panel = link.locator(
                "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' accordion ')][1]"
            )
            phase = "panel_not_ready"
            for attempt in range(3):
                if link.is_visible():
                    break
                # Resolve the control again after a redraw or an ignored click.
                control = panel.locator("a.accordion__control").first
                if (
                    control.get_attribute(
                        "aria-expanded", timeout=min(5000, remaining_ms())
                    )
                    != "true"
                ):
                    control.click(timeout=min(5000, remaining_ms()))
                try:
                    link.wait_for(state="visible", timeout=min(5000, remaining_ms()))
                    break
                except Exception:
                    if attempt == 2:
                        raise
            phase = "download_timeout"
            page.on("response", capture_response)
            with page.expect_event(
                "requestfinished",
                predicate=lambda request: (
                    response is not None and request == response.request
                ),
                timeout=remaining_ms(),
            ):
                with page.expect_download(timeout=remaining_ms()) as pending:
                    # The panel can hide again during its opening animation.
                    # Activate the discovered link without another layout wait.
                    link.evaluate("(anchor) => anchor.click()", timeout=remaining_ms())
                download = pending.value
            remaining_ms()
            path = download.path()
            remaining_ms()
            if path is None:
                self._record_failure(
                    file_url, reason="wiley_supplement_download_failed"
                )
                return None
            if response is None:
                self._record_failure(
                    file_url, reason="wiley_supplement_response_missing"
                )
                return None
            headers = _browser_response_headers(response)
            status = _browser_response_status(response)
            final_url = str(response.url)
            maximum = DEFAULT_ASSET_MAX_BYTES_PER_ASSET
            if (
                self._runtime_context is not None
                and self._runtime_context.asset_budget is not None
            ):
                maximum = self._runtime_context.asset_budget.max_bytes_per_asset
            if Path(path).stat().st_size > maximum:
                self._record_failure(
                    file_url, reason="asset_bytes_per_asset_exceeded", status=status
                )
                return None
            body = Path(path).read_bytes()
            content_type = headers.get("content-type", "")
            reason = supplementary_response_block_reason(content_type, body)
            if reason or (status is not None and status >= 400) or not body:
                self._record_response_failure(
                    file_url,
                    status=status,
                    content_type=content_type,
                    final_url=final_url,
                    body=body,
                    reason=reason or "wiley_supplement_download_failed",
                )
                return None
            return {
                "status_code": status,
                "headers": headers,
                "body": body,
                "url": final_url,
            }
        except Exception as exc:
            if response is not None:
                headers = _browser_response_headers(response)
                if "html" in headers.get("content-type", "").lower():
                    with contextlib.suppress(Exception):
                        body = response.body()
                        reason = supplementary_response_block_reason(
                            headers.get("content-type"), body
                        )
                        if reason:
                            self._record_response_failure(
                                file_url,
                                status=_browser_response_status(response),
                                content_type=headers.get("content-type", ""),
                                final_url=response.url,
                                body=body,
                                reason=reason,
                            )
                            return None
            self._record_failure(
                file_url,
                reason=f"wiley_supplement_{phase}",
                status=_browser_response_status(response)
                if response is not None
                else None,
                content_type=_browser_response_headers(response).get("content-type", "")
                if response is not None
                else "",
                final_url=str(response.url) if response is not None else str(page.url),
                error_message=normalize_text(str(exc)),
            )
            return None
        finally:
            with contextlib.suppress(Exception):
                page.remove_listener("response", capture_response)
            if download is not None:
                with contextlib.suppress(Exception):
                    download.cancel()
                with contextlib.suppress(Exception):
                    download.delete()

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
        if not referer_url:
            referer_url = normalize_text(str(getattr(self._page, "url", "") or ""))
        if not referer_url:
            referer_url = normalize_text(
                str(self._current_seed().get("browser_final_url") or "")
            )
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
        final_url = normalize_text(str(getattr(response, "url", "") or "")) or file_url
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
        browser_options=browser_options,
    )
