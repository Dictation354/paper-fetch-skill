from __future__ import annotations

import threading
from unittest import mock

from paper_fetch.providers import browser_workflow
from paper_fetch.providers.browser_workflow.fetchers import context as fetcher_context
from paper_fetch.providers.browser_workflow.fetchers import file as file_fetchers
from paper_fetch.providers.browser_workflow.fetchers import image as image_fetchers
from paper_fetch.providers.browser_workflow.fetchers.memo import (
    _MemoizedFigurePageFetcher,
)
from paper_fetch.runtime import RuntimeContext

TEST_CDP_ENDPOINT = "ws://127.0.0.1:9222/devtools/browser/test"


class _BrowserResponse:
    def __init__(
        self,
        url: str,
        body: bytes,
        content_type: str,
        *,
        status: int = 200,
    ) -> None:
        self.url = url
        self.status = status
        self.headers = {"content-type": content_type}
        self._body = body

    def all_headers(self) -> dict[str, str]:
        return dict(self.headers)

    def body(self) -> bytes:
        return self._body


def test_figure_page_memo_uses_canonical_http_url_and_caches_failures() -> None:
    underlying = mock.Mock(return_value=None)
    fetcher = _MemoizedFigurePageFetcher(underlying)

    assert (
        fetcher("HTTPS://Example.Test:443/view-large/figure/1?mode=full#viewer") is None
    )
    assert fetcher("https://example.test/view-large/figure/1?mode=full") is None

    underlying.assert_called_once_with(
        "https://example.test/view-large/figure/1?mode=full"
    )


def test_credentialed_browser_asset_cross_origin_uses_native_context_without_route() -> (
    None
):
    article_url = "https://publisher.example.test/article"
    asset_url = "https://assets.other.test/supplement.pdf"
    page = mock.Mock()
    context = mock.Mock()
    context.new_page.return_value = page
    context.cookies.return_value = []
    context.request.get.return_value = _BrowserResponse(
        asset_url,
        b"%PDF-1.7 browser-owned",
        "application/pdf",
    )
    fetcher = file_fetchers._SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: {
            "browser_final_url": article_url,
            "browser_cookies": [
                {
                    "name": "session",
                    "value": "secret",
                    "domain": "publisher.example.test",
                    "path": "/",
                }
            ],
        },
        seed_urls_getter=lambda: [article_url],
    )
    with mock.patch.object(
        fetcher_context,
        "_new_browser_context",
        return_value=(None, None, context),
    ):
        result = fetcher(asset_url, {"kind": "supplementary"})

    assert result is not None
    assert result["body"] == b"%PDF-1.7 browser-owned"
    assert result["url"] == asset_url
    context.route.assert_not_called()
    page.goto.assert_called_once_with(
        article_url,
        wait_until="domcontentloaded",
        timeout=30000,
    )
    context.request.get.assert_called_once()


def test_browser_file_fetcher_returns_browser_owned_bytes() -> None:
    first_url = "https://publisher.example.test/supplement"

    request_client = mock.Mock()
    request_client.get.return_value = _BrowserResponse(
        first_url,
        b"%PDF-1.7 browser-owned",
        "application/pdf",
    )
    fetcher = file_fetchers._SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [first_url],
    )
    fetcher._context = mock.Mock(request=request_client)

    result = fetcher._fetch_with_context_request(first_url, {})

    assert result is not None
    assert result["url"] == first_url
    assert result["body"] == b"%PDF-1.7 browser-owned"
    request_client.get.assert_called_once()


class _FakePage:
    def __init__(self) -> None:
        self.closed = False
        self.closed_by: str | None = None

    def close(self) -> None:
        self.closed = True
        self.closed_by = threading.current_thread().name

    def goto(self, *_args, **_kwargs) -> None:
        return None


class _FakeRequestClient:
    def get(
        self, *_args, **_kwargs
    ):  # pragma: no cover - request path is stubbed in tests
        raise AssertionError("unexpected request.get() call")


class _FakeContext:
    def __init__(self) -> None:
        self.closed = False
        self.closed_by: str | None = None
        self.cookies: list[dict[str, str]] = []
        self.pages: list[_FakePage] = []
        self.request = _FakeRequestClient()
        self.route_handler = None

    def route(self, pattern: str, handler) -> None:
        assert pattern == "**/*"
        self.route_handler = handler

    def add_cookies(self, cookies) -> None:
        self.cookies.extend(list(cookies))

    def new_page(self) -> _FakePage:
        page = _FakePage()
        self.pages.append(page)
        return page

    def close(self) -> None:
        self.closed = True
        self.closed_by = threading.current_thread().name


class _FakeBrowser:
    def __init__(self) -> None:
        self.closed = False
        self.closed_by: str | None = None
        self.contexts: list[_FakeContext] = []

    def new_context(self, **_kwargs) -> _FakeContext:
        context = _FakeContext()
        self.contexts.append(context)
        return context

    def close(self) -> None:
        self.closed = True
        self.closed_by = threading.current_thread().name


def test_threaded_image_fetcher_records_browser_context_exception_diagnostic() -> None:
    image_url = "https://example.test/figure.png"
    fetcher = browser_workflow._build_shared_browser_image_fetcher(
        browser_context_seed_getter=lambda: {"browser_user_agent": "UnitTestAgent/1.0"},
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        use_runtime_shared_browser=False,
    )

    try:
        with mock.patch.object(
            fetcher_context,
            "_new_browser_context",
            side_effect=RuntimeError("browser context already active"),
        ):
            result = fetcher(image_url, {"kind": "figure"})
    finally:
        fetcher.close()

    failure = fetcher.failure_for(image_url)
    assert result is None
    assert failure is not None
    assert failure["reason"] == "browser_context_error"
    assert failure["error_type"] == "RuntimeError"
    assert failure["error_message"] == "browser context already active"


def test_browser_image_fetcher_applies_budget_to_navigation_only() -> None:
    image_url = "https://example.test/figure.png"
    seed_urls = ["https://example.test/article", "https://example.test/extra"]

    class Budget:
        def exhausted(self) -> bool:
            return False

        def timeout_ms(self, requested_ms: int) -> int:
            return min(requested_ms, 1234)

        def loop_deadline(self, _max_seconds: float) -> float:
            return image_fetchers.time.monotonic()

    class RequestClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get(self, url: str, **kwargs):
            self.calls.append({"url": url, **kwargs})
            return _BrowserResponse(
                url,
                b"\x89PNG\r\n\x1a\nbudget-image",
                "image/png",
            )

    class Context:
        def __init__(self) -> None:
            self.request = RequestClient()

        def route(self, pattern: str, handler) -> None:
            assert pattern == "**/*"
            self.route_handler = handler

        def add_cookies(self, _cookies) -> None:
            return None

    class Page:
        def __init__(self) -> None:
            self.url = ""
            self.goto_calls: list[dict[str, object]] = []
            self.fetch_timeouts: list[int] = []

        def goto(self, url: str, **kwargs):
            self.url = url
            self.goto_calls.append({"url": url, **kwargs})
            return None

        def evaluate(self, script, args):
            del script, args
            raise RuntimeError("article page has no matching image")

    page = Page()
    context = Context()
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: seed_urls,
    )
    fetcher._page = page
    fetcher._context = context

    with mock.patch.object(image_fetchers, "_ImageFetchBudget", return_value=Budget()):
        result = fetcher(image_url, {"kind": "figure"})

    assert result is not None
    assert result["url"] == image_url
    assert result["body"] == b"\x89PNG\r\n\x1a\nbudget-image"
    assert [call["url"] for call in page.goto_calls] == [seed_urls[0]]
    assert all(call["timeout"] == 1234 for call in page.goto_calls)
    assert page.fetch_timeouts == []
    assert [call["url"] for call in context.request.calls] == [image_url]
    assert context.request.calls[0]["timeout"] == 1234


def test_serial_image_and_file_fetchers_share_ready_article_page_until_owner_closes() -> (
    None
):
    article_url = "https://example.test/article"
    image_url = "https://example.test/figure-large.gif"
    file_url = "https://example.test/supplement.pdf"

    class RequestClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get(self, url: str, **kwargs):
            self.calls.append({"url": url, **kwargs})
            return _BrowserResponse(
                url,
                b"%PDF-1.7 shared-browser-file",
                "application/pdf",
            )

    class Page:
        def __init__(self) -> None:
            self.url = "about:blank"
            self.goto_calls: list[str] = []
            self.close_calls = 0

        def goto(self, url: str, **_kwargs):
            self.url = url
            self.goto_calls.append(url)
            return None

        def close(self) -> None:
            self.close_calls += 1

    class Context:
        def __init__(self) -> None:
            self.request = RequestClient()
            self.page = Page()
            self.new_page_calls = 0
            self.close_calls = 0
            self.added_cookies: list[dict[str, str]] = []
            self.route_handler = None

        def route(self, pattern: str, handler) -> None:
            assert pattern == "**/*"
            self.route_handler = handler

        def add_cookies(self, cookies) -> None:
            self.added_cookies.extend(list(cookies))

        def new_page(self) -> Page:
            self.new_page_calls += 1
            return self.page

        def close(self) -> None:
            self.close_calls += 1

    context = Context()
    manager = mock.Mock()
    ready_calls: list[tuple[object, object, str]] = []
    shared_session = fetcher_context._SharedBrowserPageSession(
        preserve_seed_page=True,
        seed_page_ready_waiter=lambda page, active_context, seed_url: (
            ready_calls.append((page, active_context, seed_url)) or True
        ),
    )
    runtime_context = RuntimeContext(env={})
    previous_session = fetcher_context._replace_runtime_shared_page_session(
        runtime_context,
        shared_session,
    )
    seed = {
        "browser_cookies": [
            {
                "name": "session",
                "value": "latest",
                "domain": ".example.test",
                "path": "/",
            }
        ],
        "browser_final_url": article_url,
    }
    image_fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: seed,
        seed_urls_getter=lambda: [article_url],
        runtime_context=runtime_context,
    )
    image_fetcher._fetch_with_page = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "image/gif"},
            "body": b"GIF89a-browser-owned",
            "url": image_url,
            "dimensions": {"width": 1, "height": 1},
        }
    )
    file_fetcher = file_fetchers._SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: seed,
        seed_urls_getter=lambda: [article_url],
        runtime_context=runtime_context,
    )

    with mock.patch.object(
        fetcher_context,
        "_new_browser_context",
        return_value=(manager, None, context),
    ) as new_context:
        image_result = image_fetcher(image_url, {"kind": "figure"})
        file_result = file_fetcher(
            file_url,
            {"kind": "supplementary", "referer_url": article_url},
        )
        image_fetcher.close()
        file_fetcher.close()

    assert image_result is not None
    assert file_result is not None
    new_context.assert_called_once()
    assert context.new_page_calls == 1
    assert context.page.goto_calls == [article_url]
    assert ready_calls == [(context.page, context, article_url)]
    assert context.added_cookies == seed["browser_cookies"]
    assert [call["url"] for call in context.request.calls] == [file_url]
    assert context.request.calls[0]["headers"]["Referer"] == article_url
    assert file_result["body"] == b"%PDF-1.7 shared-browser-file"
    assert context.page.close_calls == 0
    assert context.close_calls == 0
    manager.close.assert_not_called()

    fetcher_context._restore_runtime_shared_page_session(
        runtime_context,
        shared_session,
        previous_session,
    )
    shared_session.close()
    shared_session.close()
    runtime_context.close()
    assert context.page.close_calls == 1
    assert context.close_calls == 1
    manager.close.assert_called_once()


def test_image_fetcher_does_not_navigate_shared_article_page_to_failed_asset() -> None:
    article_url = "https://example.test/article"
    image_url = "https://example.test/figure-large.gif"
    page = mock.Mock()
    page.url = article_url
    context = mock.Mock()
    shared_session = fetcher_context._SharedBrowserPageSession(preserve_seed_page=True)
    shared_session.bind(manager=None, context=context, page=page)
    shared_session.mark_seed_ready(article_url)
    runtime_context = RuntimeContext(env={})
    previous_session = fetcher_context._replace_runtime_shared_page_session(
        runtime_context,
        shared_session,
    )
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {"browser_final_url": article_url},
        seed_urls_getter=lambda: [article_url],
        runtime_context=runtime_context,
    )
    fetcher._context = context
    fetcher._page = page

    with (
        mock.patch.object(
            fetcher, "_payload_from_warmed_article_image", return_value=None
        ),
        mock.patch.object(fetcher, "_payload_from_page_fetch_url", return_value=None),
        mock.patch.object(fetcher, "_payload_from_context_request", return_value=None),
    ):
        result = fetcher._fetch_with_page(image_url)

    assert result is None
    page.goto.assert_not_called()
    fetcher_context._restore_runtime_shared_page_session(
        runtime_context,
        shared_session,
        previous_session,
    )
    shared_session.close()
    runtime_context.close()


def test_shared_page_session_closes_partial_context_when_page_creation_fails() -> None:
    image_url = "https://example.test/figure-large.gif"
    context = mock.Mock()
    context.new_page.side_effect = RuntimeError("page creation failed")
    manager = mock.Mock()
    shared_session = fetcher_context._SharedBrowserPageSession(preserve_seed_page=True)
    runtime_context = RuntimeContext(env={})
    previous_session = fetcher_context._replace_runtime_shared_page_session(
        runtime_context,
        shared_session,
    )
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: ["https://example.test/article"],
        runtime_context=runtime_context,
    )

    with mock.patch.object(
        fetcher_context,
        "_new_browser_context",
        return_value=(manager, None, context),
    ):
        result = fetcher(image_url, {"kind": "figure"})

    assert result is None
    context.close.assert_called_once()
    manager.close.assert_called_once()
    fetcher_context._restore_runtime_shared_page_session(
        runtime_context,
        shared_session,
        previous_session,
    )
    shared_session.close()
    runtime_context.close()


def test_memoized_image_fetcher_preserves_caller_thread_requirement() -> None:
    inner_fetcher = mock.Mock()
    inner_fetcher.requires_caller_thread = True
    inner_fetcher.browser_backend = "camoufox"
    fetcher = browser_workflow._MemoizedImageDocumentFetcher(inner_fetcher)

    assert fetcher.requires_caller_thread is True


def test_file_fetcher_forwards_explicit_asset_referer() -> None:
    file_url = "https://assets.example.test/supplement.docx"
    referer_url = "https://publisher.example.test/article/10.1000/example/data"
    request_client = mock.Mock()
    request_client.get.return_value = _BrowserResponse(
        file_url,
        b"PK\x03\x04browser-owned-docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    fetcher = browser_workflow._SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
    )
    fetcher._context = mock.Mock(request=request_client)

    result = fetcher._fetch_with_context_request(
        file_url,
        {"kind": "supplementary", "referer_url": referer_url},
    )

    assert result is not None
    assert result["url"] == file_url
    assert result["body"] == b"PK\x03\x04browser-owned-docx"
    request_client.get.assert_called_once_with(
        file_url,
        headers={
            "Accept": "*/*",
            "Referer": referer_url,
        },
        timeout=60000,
    )
