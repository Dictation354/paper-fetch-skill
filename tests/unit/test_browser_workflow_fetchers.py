from __future__ import annotations

import base64
import threading

import pytest
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


@pytest.mark.parametrize("provider", ["wiley", "science", None])
@pytest.mark.parametrize("size", [(22, 15), (11, 17), (519, 112)])
def test_wiley_formula_policy_is_per_call(provider, size, tmp_path) -> None:
    from paper_fetch.providers.browser_runtime.types import BrowserRuntimeConfig

    config = (
        BrowserRuntimeConfig(provider, "10.1029/test", tmp_path, True, None)
        if provider
        else None
    )
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
        browser_options=fetcher_context.BrowserDocumentFetcherOptions(
            runtime_config=config
        ),
    )
    page = mock.Mock()
    url = "https://example.test/image.png"
    calls = []

    def evaluate(script, args):
        calls.append(args)
        width, height = size
        accepted = args[3] or (width >= args[1] and height >= args[2])
        return {
            "found": True,
            "ok": accepted,
            "reason": "target_image_not_loaded",
            "url": url,
            "contentType": "image/png",
            "bodyB64": base64.b64encode(b"\x89PNG\r\n\x1a\nimage").decode(),
            "width": width,
            "height": height,
        }

    page.goto.return_value = None
    page.evaluate.side_effect = evaluate
    # End unsuccessful polling without spending the real download budget.
    page.wait_for_timeout.side_effect = RuntimeError("stop test polling")
    fetcher._page = page
    with (
        mock.patch.object(fetcher, "_ensure_page", return_value=page),
        mock.patch.object(fetcher, "_sync_context_cookies"),
        mock.patch.object(fetcher, "_warm_seed_urls"),
        mock.patch.object(fetcher, "_payload_from_page_fetch_url", return_value=None),
        mock.patch.object(fetcher, "_payload_from_context_request", return_value=None),
        mock.patch.object(fetcher, "_wait_for_primary_image", return_value=None),
    ):
        for asset in ({"kind": "formula"}, {"kind": "figure"}, {}):
            calls.clear()
            page.wait_for_timeout.reset_mock()
            result = fetcher(url, asset)
            small = provider == "wiley" and asset.get("kind") == "formula"
            target_match = provider == "wiley" and asset.get("kind") == "figure"
            assert all(args == [url, 80, 80, small, target_match] for args in calls)
            assert (result is not None) == (small or size == (519, 112))
            if result is not None:
                assert result["dimensions"] == {"width": size[0], "height": size[1]}
                page.wait_for_timeout.assert_not_called()
            assert (fetcher._min_width, fetcher._min_height) == (80, 80)


@pytest.mark.parametrize("size", [(22, 15), (11, 17), (519, 112)])
def test_small_formula_policy_reaches_readiness_and_canvas(size) -> None:
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
    )
    page = mock.Mock()
    fetcher._page = page
    url = "https://example.test/formula.png"
    width, height = size
    info = {"ready": True, "src": url, "width": width, "height": height}
    page.evaluate.side_effect = [
        info,
        {
            "ok": True,
            "url": url,
            "width": width,
            "height": height,
            "bodyB64": base64.b64encode(b"\x89PNG\r\n\x1a\nformula").decode(),
        },
    ]
    with (
        mock.patch.object(
            fetcher, "_payload_from_warmed_article_image", return_value=None
        ) as warm,
        mock.patch.object(fetcher, "_payload_from_page_fetch_url", return_value=None),
        mock.patch.object(fetcher, "_payload_from_context_request", return_value=None),
        mock.patch.object(
            fetcher, "_payload_from_navigation_response", return_value=None
        ),
    ):
        result = fetcher._fetch_with_page(url, allow_small_formula=True)
    assert result["dimensions"] == {"width": width, "height": height}
    assert page.goto.call_args.kwargs["wait_until"] == "commit"
    assert warm.call_args.kwargs["allow_small_formula"] is True
    assert page.evaluate.call_args_list[0].args[1] == [80, 80, url, True, False]
    assert page.evaluate.call_args_list[1].args[1] == [url, 80, 80, True, False]
    page.wait_for_timeout.assert_not_called()


@pytest.mark.parametrize("path", ["article", "canvas"])
@pytest.mark.parametrize("invalid", ["placeholder", "non_image"])
@pytest.mark.parametrize(
    "policy", [{"allow_small_formula": True}, {"require_target_match": True}]
)
def test_small_formula_keeps_payload_validation(path, invalid, policy) -> None:
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
    )
    url = "https://example.test/formula.png"
    page = mock.Mock()
    page.evaluate.return_value = {
        "ok": True,
        "found": True,
        "url": "https://example.test/blank.gif" if invalid == "placeholder" else url,
        "contentType": "image/png",
        "width": 22,
        "height": 15,
        "bodyB64": base64.b64encode(
            b"<html>Access denied</html>"
            if invalid == "non_image"
            else b"\x89PNG\r\n\x1a\nimage"
        ).decode(),
    }
    if path == "article":
        result = fetcher._payload_from_warmed_article_image(page, url, **policy)
    else:
        result = fetcher._payload_from_loaded_image(page, {"src": url}, **policy)
    assert result is None


@pytest.mark.parametrize("path", ["article", "canvas", "readiness"])
@pytest.mark.parametrize(
    "reason,found,width,height",
    [
        ("target_image_not_loaded", True, 22, 15),
        ("target_image_not_loaded", True, 0, 15),
        ("target_image_not_loaded", True, 22, 0),
        ("target_image_not_found", False, 640, 480),
    ],
)
def test_small_formula_rejects_unready_or_missing_target(
    path, reason, found, width, height
) -> None:
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
    )
    url = "https://example.test/formula.png"
    page = mock.Mock()
    page.url = "https://example.test/article"
    page.evaluate.return_value = {
        "ok": False,
        "ready": False,
        "found": found,
        "reason": reason,
        "width": width,
        "height": height,
        "url": url,
        "imageCount": 2,
    }
    page.wait_for_timeout.side_effect = RuntimeError("stop test polling")
    with mock.patch.object(fetcher, "_payload_from_page_fetch_url", return_value=None):
        if path == "article":
            result = fetcher._payload_from_warmed_article_image(
                page, url, allow_small_formula=True
            )
        elif path == "canvas":
            result = fetcher._payload_from_loaded_image(
                page, {"src": url}, allow_small_formula=True
            )
        else:
            result = fetcher._wait_for_primary_image(
                page, url, allow_small_formula=True
            )
    assert result is None
    if path == "article" and not found:
        page.wait_for_timeout.assert_not_called()


@pytest.mark.parametrize("provider", ["wiley", "science", None])
def test_formula_navigation_policy_is_per_call(provider, tmp_path) -> None:
    from paper_fetch.providers.browser_runtime.types import BrowserRuntimeConfig

    config = (
        BrowserRuntimeConfig(provider, "10.1029/test", tmp_path, True, None)
        if provider
        else None
    )
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
        browser_options=fetcher_context.BrowserDocumentFetcherOptions(
            runtime_config=config
        ),
    )
    url = "https://example.test/formula.png"
    page = mock.Mock()
    fetcher._page = page
    body = b"\x89PNG\r\n\x1a\nformula"
    response = _BrowserResponse(url, body, "image/png")
    page.goto.return_value = response
    with (
        mock.patch.object(fetcher, "_ensure_page", return_value=page),
        mock.patch.object(fetcher, "_sync_context_cookies"),
        mock.patch.object(fetcher, "_warm_seed_urls"),
        mock.patch.object(
            fetcher, "_payload_from_warmed_article_image", return_value=None
        ),
        mock.patch.object(fetcher, "_payload_from_page_fetch_url", return_value=None),
        mock.patch.object(fetcher, "_payload_from_context_request", return_value=None),
        mock.patch.object(
            fetcher,
            "_wait_for_primary_image",
            return_value={"ready": True, "src": url, "width": 22, "height": 15},
        ) as readiness,
        mock.patch.object(response, "body", wraps=response.body) as response_body,
    ):
        order = mock.Mock()
        order.attach_mock(page.goto, "goto")
        order.attach_mock(readiness, "readiness")
        order.attach_mock(response_body, "body")
        for asset in ({"kind": "formula"}, {"kind": "figure"}, {}, {"kind": "formula"}):
            order.reset_mock()
            result = fetcher(url, asset)
            small = provider == "wiley" and asset.get("kind") == "formula"
            assert result["body"] == body
            figure = provider == "wiley" and asset.get("kind") == "figure"
            assert page.goto.call_args.kwargs["wait_until"] == (
                "commit" if small or figure else "domcontentloaded"
            )
            assert 0 < page.goto.call_args.kwargs["timeout"] <= 10000
            assert [call[0] for call in order.mock_calls] == (
                ["goto", "readiness", "body"] if small or figure else ["goto", "body"]
            )
            if small:
                assert readiness.call_args.kwargs["allow_small_formula"] is True
            if figure:
                assert readiness.call_args.kwargs["allow_small_formula"] is False
                assert readiness.call_args.kwargs["require_target_match"] is True
                assert (fetcher._min_width, fetcher._min_height) == (80, 80)
            assert fetcher._active_image_fetch_budget is None


@pytest.mark.parametrize("ready", [False, True])
@pytest.mark.parametrize("navigation", ["image", "non_image", "placeholder"])
@pytest.mark.parametrize("figure", [False, True])
def test_formula_navigation_requires_readiness_and_valid_response(
    ready, navigation, figure
) -> None:
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
    )
    if figure:
        from types import SimpleNamespace

        fetcher._browser_config = SimpleNamespace(provider="wiley")
    url = "https://example.test/formula.png"
    page = mock.Mock()
    fetcher._page = page
    response = _BrowserResponse(
        "https://example.test/blank.gif" if navigation == "placeholder" else url,
        b"<html>Access denied</html>"
        if navigation == "non_image"
        else b"\x89PNG\r\n\x1a\nformula",
        "text/html" if navigation == "non_image" else "image/png",
    )
    page.goto.return_value = response
    page.evaluate.return_value = {
        "ready": ready,
        "src": url,
        "width": 1200 if figure else 22,
        "height": 900 if figure else 15,
    }
    page.wait_for_timeout.side_effect = RuntimeError("stop test polling")
    with (
        mock.patch.object(
            fetcher, "_payload_from_warmed_article_image", return_value=None
        ),
        mock.patch.object(fetcher, "_payload_from_page_fetch_url", return_value=None),
        mock.patch.object(fetcher, "_payload_from_context_request", return_value=None),
        mock.patch.object(
            fetcher, "_payload_from_page_fetch", return_value=None
        ) as export,
        mock.patch.object(response, "body", wraps=response.body) as response_body,
    ):
        result = fetcher._fetch_with_page(
            url,
            allow_small_formula=not figure,
            require_target_match=figure,
        )
    assert (result is not None) == (ready and navigation == "image")
    if not ready:
        response_body.assert_not_called()
        export.assert_not_called()
    else:
        response_body.assert_called_once()
        assert export.call_count == (navigation != "image")


@pytest.mark.parametrize(
    "recovery", ["article", "fetch", "request", "navigation", "canvas"]
)
def test_wiley_figure_target_match_recovery_order(recovery) -> None:
    url = "https://example.test/full.png"
    body = b"\x89PNG\r\n\x1a\nfull"
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {}, seed_urls_getter=lambda: []
    )
    page = mock.Mock()
    fetcher._page = page
    rendered = {
        "ok": True,
        "found": True,
        "url": url,
        "contentType": "image/png",
        "bodyB64": base64.b64encode(body).decode(),
        "width": 1200,
        "height": 900,
    }
    info = {"ready": True, "src": url, "width": 1200, "height": 900}
    page.evaluate.side_effect = [
        rendered if recovery == "article" else {"found": False},
        info,
        rendered,
    ]
    payload = {"body": body, "url": url}
    page.goto.return_value = (
        _BrowserResponse("https://example.test/redirected-full.png", body, "image/png")
        if recovery == "navigation"
        else None
    )
    with (
        mock.patch.object(
            fetcher,
            "_payload_from_page_fetch_url",
            return_value=payload if recovery == "fetch" else None,
        ) as fetch,
        mock.patch.object(
            fetcher,
            "_payload_from_context_request",
            return_value=payload if recovery == "request" else None,
        ) as request,
    ):
        result = fetcher._fetch_with_page(url, require_target_match=True)
    assert result["body"] == body
    assert fetch.call_count == (
        0 if recovery == "article" else 2 if recovery == "canvas" else 1
    )
    assert request.call_count == (recovery not in {"article", "fetch"})
    assert page.goto.call_count == (recovery in {"navigation", "canvas"})
    assert page.evaluate.call_args_list[0].args[1] == [url, 80, 80, False, True]
    if recovery == "canvas":
        assert page.evaluate.call_args_list[1].args[1] == [80, 80, url, False, True]
        assert page.evaluate.call_args_list[2].args[1] == [url, 80, 80, False, True]
    if recovery == "navigation":
        assert result["url"] == "https://example.test/redirected-full.png"
    page.wait_for_timeout.assert_not_called()


@pytest.mark.browser
def test_wiley_picture_uses_loaded_target_at_both_viewports(monkeypatch):
    import json
    import os
    from pathlib import Path

    from paper_fetch.extraction.image_payloads import image_dimensions_from_bytes
    from paper_fetch.providers.browser_workflow.fetchers.scripts import (
        _ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT,
        _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
    )
    from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR

    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, utils

    # Pytest isolates the managed cache; read the existing executable's version
    # without asking Camoufox to discover or install a runtime in that cache.
    version_file = next(
        parent / "version.json"
        for parent in Path(executable).parents
        if (parent / "version.json").is_file()
    )
    version = json.loads(version_file.read_text())["version"]
    monkeypatch.setattr(utils, "installed_verstr", lambda: version)

    fixtures = Path(__file__).parents[1] / "fixtures" / "golden_criteria"
    full = (
        fixtures / "10.1371_journal.pone.0015338/body_assets/pone.0015338.g002.png"
    ).read_bytes()
    preview = (
        fixtures / "10.1063_5.0129134/body_assets/m_125205_1_f4.jpeg"
    ).read_bytes()
    target = "https://example.test/full.png"
    html = '<picture><source media="(min-width: 1600px)" srcset="/full.png"><img id="target" src="/preview.jpg"></picture>'
    fetcher = image_fetchers._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {}, seed_urls_getter=lambda: []
    )
    fake = mock.Mock()
    fake.evaluate.return_value = {"ready": True}
    fetcher._wait_for_primary_image(fake, target, require_target_match=True)
    readiness_script = fake.evaluate.call_args.args[0]

    def route_asset(route):
        url = route.request.url
        if url.endswith("/article"):
            route.fulfill(body=html, content_type="text/html")
        else:
            route.fulfill(
                body=full if url == target else preview,
                content_type="image/png" if url == target else "image/jpeg",
            )

    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as browser:
        for width in (1280, 1920):
            context = browser.new_context(viewport={"width": width, "height": 1080})
            context.route("https://example.test/**", route_asset)
            page = context.new_page()
            page.goto("https://example.test/article")
            page.locator("#target").evaluate("(image) => image.decode()")
            expected_src = (
                target if width == 1920 else "https://example.test/preview.jpg"
            )
            assert (
                page.locator("#target").evaluate("(image) => image.currentSrc")
                == expected_src
            )
            fetcher._page = page
            fetcher._context = context
            with mock.patch.object(
                page,
                "wait_for_timeout",
                side_effect=AssertionError("unexpected image wait"),
            ):
                warmed = fetcher._payload_from_warmed_article_image(
                    page, target, require_target_match=True
                )
                assert (warmed is not None) == (width == 1920)
                payload = fetcher._fetch_with_page(target, require_target_match=True)
            assert payload["url"] == target
            assert image_dimensions_from_bytes(payload["body"]) == (2068, 470)
            # A target declared only in picture sources is also rejected by
            # post-navigation readiness and the loaded-image canvas script.
            page.goto("https://example.test/article")
            page.locator("#target").evaluate("(image) => image.decode()")
            for script in (
                _ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT,
                _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
            ):
                result = page.evaluate(script, [target, 80, 80, False, True])
                assert bool(result.get("ok")) == (width == 1920)
            ready = page.evaluate(readiness_script, [80, 80, target, False, True])
            assert ready["ready"] == (width == 1920)
            if width == 1920:
                page.evaluate("""async () => {
                    const other = new Image(); other.src = '/other.jpg';
                    document.body.append(other); await other.decode();
                }""")
                for mode in (
                    "incomplete",
                    "zero_width",
                    "zero_height",
                    "tiny",
                    "empty",
                    "missing",
                ):
                    page.locator("#target").evaluate(
                        """(image, mode) => {
                        for (const key of ['complete', 'naturalWidth', 'naturalHeight']) delete image[key];
                        const changes = {incomplete: ['complete', false], zero_width: ['naturalWidth', 0],
                            zero_height: ['naturalHeight', 0], tiny: ['naturalWidth', 22]};
                        if (changes[mode]) Object.defineProperty(image, changes[mode][0],
                            {value: changes[mode][1], configurable: true});
                        if (mode === 'missing') image.remove();
                    }""",
                        mode,
                    )
                    candidate = "" if mode == "empty" else target
                    for script in (
                        _ARTICLE_IMAGE_CANVAS_EXPORT_SCRIPT,
                        _LOADED_IMAGE_CANVAS_EXPORT_SCRIPT,
                    ):
                        result = page.evaluate(script, [candidate, 80, 80, False, True])
                        assert not result.get("ok"), (mode, result)
                    ready = page.evaluate(
                        readiness_script, [80, 80, candidate, False, True]
                    )
                    assert not ready["ready"], (mode, ready)
            context.close()


@pytest.mark.parametrize(
    "collapsed, outcome",
    [
        (True, "download"),
        (False, "download"),
        (True, "transfer_timeout"),
        (False, "challenge"),
        (True, "first_click_ignored"),
        (True, "delayed_links"),
        (True, "never_expands"),
    ],
)
def test_wiley_file_fetcher_clicks_supporting_panel_and_preserves_response(
    tmp_path, collapsed, outcome
):
    from types import SimpleNamespace

    url = "https://onlinelibrary.wiley.com/action/downloadSupplement?doi=10.1111/test&file=si.docx"
    article_url = "https://onlinelibrary.wiley.com/doi/full/10.1111/test"
    file_path = tmp_path / "browser-download"
    file_path.write_bytes(b"PK\x03\x04supplement")
    response = _BrowserResponse(url, file_path.read_bytes(), "application/octet-stream")
    if outcome == "challenge":
        response = _BrowserResponse(
            url, b"<title>Just a moment...</title>", "text/html", status=403
        )
    response.request = SimpleNamespace(url=url, redirected_from=None)
    page = mock.Mock(url=article_url)
    link = page.locator.return_value.locator.return_value.first
    link.is_visible.return_value = not collapsed
    control = link.locator.return_value.locator.return_value.first
    control.get_attribute.return_value = "false"
    visible_waits = 0

    def wait_for_link(*, state, timeout):
        nonlocal visible_waits
        if state != "visible":
            return
        visible_waits += 1
        if outcome == "never_expands" or (
            outcome in {"first_click_ignored", "delayed_links"} and visible_waits == 1
        ):
            assert 0 < timeout <= 5000
            if outcome == "delayed_links":
                control.get_attribute.return_value = "true"
            raise TimeoutError("panel not ready")
        link.is_visible.return_value = True

    link.wait_for.side_effect = wait_for_link
    download = mock.Mock(url=url)
    download.path.return_value = str(file_path)
    page.expect_event.return_value.__enter__ = mock.Mock()
    page.expect_event.return_value.__exit__ = mock.Mock(return_value=False)
    page.expect_download.return_value.__enter__ = mock.Mock(
        return_value=SimpleNamespace(value=download)
    )
    page.expect_download.return_value.__exit__ = mock.Mock(return_value=False)
    if outcome == "transfer_timeout":
        page.expect_event.return_value.__exit__.side_effect = TimeoutError(
            "transfer stalled"
        )
    elif outcome == "challenge":
        page.expect_download.return_value.__exit__.side_effect = TimeoutError(
            "no download"
        )
    callbacks = {}
    page.on.side_effect = lambda event, callback: callbacks.update({event: callback})

    def activate_link(expression, **kwargs):
        callbacks["response"](response)

    link.evaluate.side_effect = activate_link
    fetcher = file_fetchers._SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: {"browser_final_url": article_url},
        seed_urls_getter=lambda: [article_url],
        browser_options=fetcher_context.BrowserDocumentFetcherOptions(
            runtime_config=SimpleNamespace(provider="wiley")
        ),
    )
    fetcher._page = page
    fetcher._context = mock.Mock()
    with mock.patch.object(
        file_fetchers,
        "wait_for_atypon_body_dom_ready",
        return_value=SimpleNamespace(ready=True),
    ):
        result = fetcher(url, {"kind": "supplementary"})
    if outcome in {"download", "first_click_ignored", "delayed_links"}:
        assert result == {
            "status_code": 200,
            "headers": response.headers,
            "body": file_path.read_bytes(),
            "url": url,
        }
    elif outcome == "never_expands":
        assert result is None
        assert fetcher.failure_for(url)["reason"] == "wiley_supplement_panel_not_ready"
        assert control.click.call_count == 3
        link.click.assert_not_called()
        link.evaluate.assert_not_called()
        page.expect_download.assert_not_called()
        return
    else:
        assert result is None
        assert fetcher.failure_for(url)["reason"] == (
            "cloudflare_challenge"
            if outcome == "challenge"
            else "wiley_supplement_download_timeout"
        )
        assert fetcher.failure_for(url)["status"] == response.status
        download.path.assert_not_called()
    assert control.click.call_count == (
        2 if outcome == "first_click_ignored" else int(collapsed)
    )
    link.click.assert_not_called()
    link.evaluate.assert_called_once()
    fetcher._context.request.get.assert_not_called()
    page.goto.assert_not_called()
    if outcome != "challenge":
        download.cancel.assert_called_once()
        download.delete.assert_called_once()
    page.remove_listener.assert_called_once()


@pytest.mark.parametrize(
    "ready, challenge, expected",
    [
        (False, True, "cloudflare_challenge"),
        (False, False, "wiley_supplement_article_not_ready"),
        (True, False, "wiley_supplement_download_timeout"),
    ],
)
def test_wiley_file_click_reports_challenge_readiness_and_timeout(
    ready, challenge, expected
):
    from types import SimpleNamespace

    page = mock.Mock(url="https://onlinelibrary.wiley.com/doi/full/10.1111/test")
    page.content.return_value = (
        "<title>Just a moment...</title>"
        if challenge
        else "<article>Not ready</article>"
    )
    page.locator.return_value.locator.return_value.first.is_visible.return_value = True
    page.expect_event.side_effect = TimeoutError("download timed out")
    fetcher = file_fetchers._SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
    )
    fetcher._page = page
    with mock.patch.object(
        file_fetchers,
        "wait_for_atypon_body_dom_ready",
        return_value=SimpleNamespace(ready=ready),
    ):
        assert (
            fetcher._fetch_wiley_with_page_click(
                "https://onlinelibrary.wiley.com/si.docx", {}
            )
            is None
        )
    assert (
        fetcher.failure_for("https://onlinelibrary.wiley.com/si.docx")["reason"]
        == expected
    )


def test_wiley_file_click_caps_operations_by_remaining_request_budget():
    from types import SimpleNamespace

    context = RuntimeContext(env={})
    context.initialize_deadline(2)
    page = mock.Mock(url="https://onlinelibrary.wiley.com/doi/full/10.1111/test")
    fetcher = file_fetchers._SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
        runtime_context=context,
    )
    fetcher._page = page
    page.content.return_value = "<article>Not ready</article>"
    with mock.patch.object(
        file_fetchers,
        "wait_for_atypon_body_dom_ready",
        return_value=SimpleNamespace(ready=False),
    ) as wait:
        assert (
            fetcher._fetch_wiley_with_page_click(
                "https://onlinelibrary.wiley.com/si.docx", {}
            )
            is None
        )
    assert 0 < wait.call_args.kwargs["timeout_seconds"] <= 2


@pytest.mark.browser
@pytest.mark.parametrize(
    "ignored_click, reclose_after_visible",
    [(False, False), (True, False), (False, True)],
)
def test_wiley_click_survives_collapsed_panel_redraw_in_browser(
    monkeypatch, ignored_click, reclose_after_visible
):
    import json
    import os
    from pathlib import Path
    from types import SimpleNamespace

    from tests._environment import PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR

    executable = os.environ.get(PRESERVED_CAMOUFOX_EXECUTABLE_ENV_VAR)
    if not executable or not Path(executable).is_file():
        pytest.skip("requires the existing local Camoufox executable")
    camoufox = pytest.importorskip("camoufox.sync_api")
    from camoufox import DefaultAddons, pkgman, utils

    version_file = next(
        parent / "version.json"
        for parent in Path(executable).parents
        if (parent / "version.json").is_file()
    )
    monkeypatch.setattr(
        utils,
        "installed_verstr",
        lambda: json.loads(version_file.read_text())["version"],
    )
    # Font/config resources must use the preserved runtime too, not the
    # isolated empty cache where Camoufox would try an online installation.
    monkeypatch.setattr(pkgman, "camoufox_path", lambda: version_file.parent)
    article_url = "https://example.test/article"
    file_url = "https://example.test/supplement.docx"
    body = b"PK\x03\x04real-browser-supplement"
    html = (
        """<section class="article-section__content"><h2>Results</h2><p>"""
        + "Article body. " * 120
        + """</p><p>Second paragraph.</p></section>
    <section class="article-section__supporting"><div class="accordion">
      <a class="accordion__control" aria-expanded="false" onclick="this.parentElement.innerHTML='<a href=/supplement.docx download>Supporting file</a>'">Supporting Information</a>
      <div hidden><a href="/supplement.docx" download>Supporting file</a></div>
    </div></section>"""
    )
    if ignored_click:
        # The initial control is replaced before its delayed handler is ready.
        html = html.replace(
            'onclick="this.parentElement.innerHTML=',
            "onclick=\"if (!this.dataset.ready) { const replacement = this.cloneNode(true); this.replaceWith(replacement); setTimeout(() => replacement.dataset.ready = 'true', 200); return; } this.parentElement.innerHTML=",
        )
    reclosed = []
    if reclose_after_visible:
        from playwright.sync_api import Locator

        original_wait_for = Locator.wait_for

        def wait_then_reclose(locator, **kwargs):
            result = original_wait_for(locator, **kwargs)
            if kwargs.get("state") == "visible":
                # Reproduce the live page hiding the panel after visibility
                # succeeds but before the download action starts.
                locator.evaluate(
                    "(anchor) => anchor.closest('.accordion').style.display = 'none'"
                )
                reclosed.append(not locator.is_visible())
            return result

        monkeypatch.setattr(Locator, "wait_for", wait_then_reclose)
    requests = []
    finished = []

    def route_asset(route):
        requests.append(route.request.url)
        if route.request.url == article_url:
            route.fulfill(body=html, content_type="text/html")
        else:
            route.fulfill(
                body=body,
                content_type="application/octet-stream",
                headers={
                    "Content-Disposition": 'attachment; filename="supplement.docx"'
                },
            )

    with camoufox.Camoufox(
        headless=True, executable_path=executable, exclude_addons=list(DefaultAddons)
    ) as browser:
        context = browser.new_context()
        context.route("https://example.test/**", route_asset)
        page = context.new_page()
        page.on("requestfinished", lambda request: finished.append(request.url))
        page.goto(article_url)
        fetcher = file_fetchers._SharedBrowserFileDocumentFetcher(
            browser_context_seed_getter=lambda: {"browser_final_url": article_url},
            seed_urls_getter=lambda: [article_url],
            browser_options=fetcher_context.BrowserDocumentFetcherOptions(
                runtime_config=SimpleNamespace(provider="wiley")
            ),
        )
        fetcher._page = page
        fetcher._context = context
        result = fetcher(file_url, {"kind": "supplementary"})
        assert result is not None, fetcher.failure_for(file_url)
        assert result["body"] == body
        assert result["status_code"] == 200
        assert (
            result["headers"]["content-disposition"]
            == 'attachment; filename="supplement.docx"'
        )
        assert requests.count(file_url) == 1
        assert file_url in finished, "download request does not emit requestfinished"
        assert reclosed == ([True] if reclose_after_visible else [])
        context.close()
