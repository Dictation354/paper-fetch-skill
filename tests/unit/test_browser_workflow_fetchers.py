from __future__ import annotations

import sys
import threading
import types
from unittest import mock

from paper_fetch.providers import browser_workflow
from paper_fetch.providers.browser_workflow.fetchers import context as fetcher_context
from paper_fetch.providers.browser_workflow.fetchers import image as image_fetchers
from paper_fetch.runtime import RuntimeContext

TEST_CDP_ENDPOINT = "ws://127.0.0.1:9222/devtools/browser/test"


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


def _fake_playwright_cdp_modules(
    browsers: list[_FakeBrowser],
) -> dict[str, types.ModuleType]:
    playwright_module = types.ModuleType("playwright")
    sync_api_module = types.ModuleType("playwright.sync_api")

    class _FakeChromium:
        def connect_over_cdp(self, _endpoint: str) -> _FakeBrowser:
            browser = _FakeBrowser()
            browsers.append(browser)
            return browser

    class _FakePlaywright:
        def __init__(self) -> None:
            self.chromium = _FakeChromium()

        def stop(self) -> None:
            return None

    class _FakeSyncPlaywright:
        def start(self) -> _FakePlaywright:
            return _FakePlaywright()

    def sync_playwright() -> _FakeSyncPlaywright:
        return _FakeSyncPlaywright()

    sync_api_module.sync_playwright = sync_playwright
    playwright_module.sync_api = sync_api_module
    return {"playwright": playwright_module, "playwright.sync_api": sync_api_module}


def _runtime_context_with_cdp_and_forbidden_shared_browser() -> RuntimeContext:
    context = RuntimeContext(env={})
    context.new_browser_context = mock.Mock(
        side_effect=AssertionError("shared runtime browser should not be used")
    )
    return context


def test_threaded_image_fetcher_uses_thread_private_browser_when_runtime_context_exists() -> (
    None
):
    runtime_context = _runtime_context_with_cdp_and_forbidden_shared_browser()
    browsers: list[_FakeBrowser] = []
    fetcher = browser_workflow._build_shared_browser_image_fetcher(
        browser_context_seed_getter=lambda: {
            "browser_cookies": [
                {
                    "name": "cf_clearance",
                    "value": "seed",
                    "domain": ".example.test",
                    "path": "/",
                }
            ],
            "browser_user_agent": "UnitTestAgent/1.0",
        },
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=False,
        cdp_endpoint=TEST_CDP_ENDPOINT,
    )
    inner_fetcher = fetcher._get_fetcher()
    inner_fetcher._fetch_with_page = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": b"\x89PNG\r\n\x1a\nthread-private-image",
            "url": "https://example.test/figure.png",
            "dimensions": {"width": 640, "height": 480},
        }
    )

    try:
        with mock.patch.dict(sys.modules, _fake_playwright_cdp_modules(browsers)):
            result = fetcher("https://example.test/figure.png", {"kind": "figure"})
    finally:
        fetcher.close()
        fetcher.close()

    assert fetcher.requires_caller_thread is False
    assert result is not None
    runtime_context.new_browser_context.assert_not_called()
    assert len(browsers) == 1
    browser = browsers[0]
    assert browser.closed is True
    assert len(browser.contexts) == 1
    assert browser.contexts[0].closed is True
    assert len(browser.contexts[0].pages) == 1
    assert browser.contexts[0].pages[0].closed is True


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


def test_browser_image_fetcher_applies_per_image_budget_to_browser_steps() -> None:
    image_url = "https://example.test/figure.png"
    seed_urls = ["https://example.test/article", "https://example.test/extra"]

    class Budget:
        def exhausted(self) -> bool:
            return False

        def timeout_ms(self, requested_ms: int) -> int:
            return min(requested_ms, 1234)

        def loop_deadline(self, _max_seconds: float) -> float:
            return image_fetchers.time.monotonic()

    class Response:
        status = 200
        url = image_url
        headers = {"content-type": "text/html"}

        def body(self) -> bytes:
            return b"<html><title>Not an image</title></html>"

    class RequestClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get(self, url: str, **kwargs):
            self.calls.append({"url": url, **kwargs})
            return Response()

    class Context:
        def __init__(self) -> None:
            self.request = RequestClient()

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
            return Response()

        def evaluate(self, script, args):
            if "fetch(imageSrc" in str(script):
                self.fetch_timeouts.append(int(args[1]))
                return {"ok": False, "error": "AbortError", "timedOut": True}
            raise AssertionError("wait loops should be skipped by the fake budget")

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

    assert result is None
    assert [call["url"] for call in page.goto_calls] == [
        seed_urls[0],
        image_url,
        seed_urls[0],
        image_url,
    ]
    assert all(call["timeout"] == 1234 for call in page.goto_calls)
    assert page.fetch_timeouts == [1234, 1234]
    assert [call["timeout"] for call in context.request.calls] == [1234, 1234]


def test_image_fetcher_passes_cdp_endpoint_to_context_factory() -> None:
    image_url = "https://example.test/figure.png"
    fake_context = _FakeContext()
    fake_manager = mock.Mock()
    context_calls: list[dict[str, object]] = []

    def new_browser_context(**kwargs):
        context_calls.append(dict(kwargs))
        return fake_manager, None, fake_context

    fetcher = browser_workflow._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {"browser_user_agent": "UnitTestAgent/1.0"},
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        use_runtime_shared_browser=False,
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
    )
    fetcher._fetch_with_page = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": b"\x89PNG\r\n\x1a\ncdp-image",
            "url": image_url,
            "dimensions": {"width": 640, "height": 480},
        }
    )

    try:
        with mock.patch.object(
            fetcher_context, "_new_browser_context", side_effect=new_browser_context
        ):
            result = fetcher(image_url, {"kind": "figure"})
    finally:
        fetcher.close()

    assert result is not None
    assert context_calls == [
        {
            "runtime_context": None,
            "headless": True,
            "user_agent": "UnitTestAgent/1.0",
            "use_runtime_shared_browser": False,
            "binary_path": None,
            "cdp_endpoint": "ws://127.0.0.1:9222/devtools/browser/test",
            "profile_dir": None,
            "user_data_dir": None,
        }
    ]
    fake_manager.close.assert_called_once()


def test_image_fetcher_uses_runtime_keyed_context_when_shared_browser_enabled() -> None:
    image_url = "https://example.test/figure.png"
    fake_context = _FakeContext()
    runtime_context = RuntimeContext(env={})
    runtime_context.new_browser_context_for_config = mock.Mock(
        return_value=fake_context
    )
    fetcher = browser_workflow._SharedBrowserImageDocumentFetcher(
        browser_context_seed_getter=lambda: {"browser_user_agent": "UnitTestAgent/1.0"},
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=True,
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
    )
    fetcher._fetch_with_page = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "image/png"},
            "body": b"\x89PNG\r\n\x1a\nshared-runtime-image",
            "url": image_url,
            "dimensions": {"width": 640, "height": 480},
        }
    )

    try:
        result = fetcher(image_url, {"kind": "figure"})
    finally:
        fetcher.close()
        runtime_context.close()

    assert result is not None
    assert fetcher.requires_caller_thread is True
    runtime_context.new_browser_context_for_config.assert_called_once()
    call_kwargs = runtime_context.new_browser_context_for_config.call_args.kwargs
    assert call_kwargs["cdp_endpoint"] == "ws://127.0.0.1:9222/devtools/browser/test"
    assert call_kwargs["user_agent"] == "UnitTestAgent/1.0"
    assert fake_context.closed is True


def test_memoized_image_fetcher_preserves_caller_thread_requirement() -> None:
    inner_fetcher = mock.Mock()
    inner_fetcher.requires_caller_thread = True
    inner_fetcher.browser_backend = "camoufox"
    fetcher = browser_workflow._MemoizedImageDocumentFetcher(inner_fetcher)

    assert fetcher.requires_caller_thread is True


def test_threaded_file_fetcher_uses_thread_private_browser_when_runtime_context_exists() -> (
    None
):
    runtime_context = _runtime_context_with_cdp_and_forbidden_shared_browser()
    browsers: list[_FakeBrowser] = []
    fetcher = browser_workflow._build_shared_browser_file_fetcher(
        browser_context_seed_getter=lambda: {
            "browser_cookies": [
                {
                    "name": "cf_clearance",
                    "value": "seed",
                    "domain": ".example.test",
                    "path": "/",
                }
            ],
            "browser_user_agent": "UnitTestAgent/1.0",
        },
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=False,
        cdp_endpoint=TEST_CDP_ENDPOINT,
        thread_local=True,
    )
    inner_fetcher = fetcher._get_fetcher()
    inner_fetcher._fetch_with_context_request = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "application/pdf"},
            "body": b"%PDF-1.7 thread-private-file",
            "url": "https://example.test/supplement.pdf",
        }
    )

    try:
        with mock.patch.dict(sys.modules, _fake_playwright_cdp_modules(browsers)):
            result = fetcher(
                "https://example.test/supplement.pdf", {"kind": "supplementary"}
            )
    finally:
        fetcher.close()
        fetcher.close()

    assert result is not None
    runtime_context.new_browser_context.assert_not_called()
    assert len(browsers) == 1
    browser = browsers[0]
    assert browser.closed is True
    assert len(browser.contexts) == 1
    assert browser.contexts[0].closed is True
    assert len(browser.contexts[0].pages) == 1
    assert browser.contexts[0].pages[0].closed is True


def test_file_fetcher_passes_cdp_endpoint_to_context_factory() -> None:
    file_url = "https://example.test/supplement.pdf"
    fake_context = _FakeContext()
    fake_manager = mock.Mock()
    context_calls: list[dict[str, object]] = []

    def new_browser_context(**kwargs):
        context_calls.append(dict(kwargs))
        return fake_manager, None, fake_context

    fetcher = browser_workflow._SharedBrowserFileDocumentFetcher(
        browser_context_seed_getter=lambda: {"browser_user_agent": "UnitTestAgent/1.0"},
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        use_runtime_shared_browser=False,
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
    )
    fetcher._fetch_with_context_request = mock.Mock(
        return_value={
            "status_code": 200,
            "headers": {"content-type": "application/pdf"},
            "body": b"%PDF-1.7 cdp-file",
            "url": file_url,
        }
    )

    try:
        with mock.patch.object(
            fetcher_context, "_new_browser_context", side_effect=new_browser_context
        ):
            result = fetcher(file_url, {"kind": "supplementary"})
    finally:
        fetcher.close()

    assert result is not None
    assert context_calls == [
        {
            "runtime_context": None,
            "headless": True,
            "user_agent": "UnitTestAgent/1.0",
            "use_runtime_shared_browser": False,
            "binary_path": None,
            "cdp_endpoint": "ws://127.0.0.1:9222/devtools/browser/test",
            "profile_dir": None,
            "user_data_dir": None,
        }
    ]
    fake_manager.close.assert_called_once()


def test_file_fetcher_forwards_explicit_asset_referer() -> None:
    file_url = "https://assets.example.test/supplement.docx"
    referer_url = "https://publisher.example.test/article/10.1000/example/data"
    response = mock.Mock(status=200, url=file_url)
    response.all_headers.return_value = {
        "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
    response.body.return_value = b"PK\x03\x04example-docx"
    request_client = mock.Mock()
    request_client.get.return_value = response
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
    request_client.get.assert_called_once_with(
        file_url,
        headers={"Accept": "*/*", "Referer": referer_url},
        timeout=60000,
    )


def test_threaded_image_fetcher_closes_thread_private_browser_on_worker_thread() -> (
    None
):
    runtime_context = _runtime_context_with_cdp_and_forbidden_shared_browser()
    browsers: list[_FakeBrowser] = []
    fetcher = browser_workflow._build_shared_browser_image_fetcher(
        browser_context_seed_getter=lambda: {"browser_user_agent": "UnitTestAgent/1.0"},
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=False,
        cdp_endpoint=TEST_CDP_ENDPOINT,
    )
    errors: list[BaseException] = []
    result_holder: dict[str, object] = {}

    def run_fetch() -> None:
        try:
            result_holder["result"] = fetcher(
                "https://example.test/figure.png", {"kind": "figure"}
            )
        except (
            BaseException
        ) as exc:  # pragma: no cover - assertion reports the captured exception
            errors.append(exc)

    with (
        mock.patch.dict(sys.modules, _fake_playwright_cdp_modules(browsers)),
        mock.patch.object(
            browser_workflow._SharedBrowserImageDocumentFetcher,
            "_fetch_with_page",
            return_value={
                "status_code": 200,
                "headers": {"content-type": "image/png"},
                "body": b"\x89PNG\r\n\x1a\nthread-private-image",
                "url": "https://example.test/figure.png",
                "dimensions": {"width": 640, "height": 480},
            },
        ),
    ):
        worker = threading.Thread(target=run_fetch, name="asset-worker")
        worker.start()
        worker.join()
        fetcher.close()

    assert errors == []
    assert result_holder["result"] is not None
    runtime_context.new_browser_context.assert_not_called()
    assert len(browsers) == 1
    browser = browsers[0]
    assert browser.closed is True
    assert browser.closed_by == "asset-worker"
    assert browser.contexts[0].closed_by == "asset-worker"
    assert browser.contexts[0].pages[0].closed_by == "asset-worker"


def test_threaded_file_fetcher_closes_thread_private_browser_on_worker_thread() -> None:
    runtime_context = _runtime_context_with_cdp_and_forbidden_shared_browser()
    browsers: list[_FakeBrowser] = []
    fetcher = browser_workflow._build_shared_browser_file_fetcher(
        browser_context_seed_getter=lambda: {"browser_user_agent": "UnitTestAgent/1.0"},
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=False,
        cdp_endpoint=TEST_CDP_ENDPOINT,
        thread_local=True,
    )
    errors: list[BaseException] = []
    result_holder: dict[str, object] = {}

    def run_fetch() -> None:
        try:
            result_holder["result"] = fetcher(
                "https://example.test/supplement.pdf", {"kind": "supplementary"}
            )
        except (
            BaseException
        ) as exc:  # pragma: no cover - assertion reports the captured exception
            errors.append(exc)

    with (
        mock.patch.dict(sys.modules, _fake_playwright_cdp_modules(browsers)),
        mock.patch.object(
            browser_workflow._SharedBrowserFileDocumentFetcher,
            "_fetch_with_context_request",
            return_value={
                "status_code": 200,
                "headers": {"content-type": "application/pdf"},
                "body": b"%PDF-1.7 thread-private-file",
                "url": "https://example.test/supplement.pdf",
            },
        ),
    ):
        worker = threading.Thread(target=run_fetch, name="asset-worker")
        worker.start()
        worker.join()
        fetcher.close()

    assert errors == []
    assert result_holder["result"] is not None
    runtime_context.new_browser_context.assert_not_called()
    assert len(browsers) == 1
    browser = browsers[0]
    assert browser.closed is True
    assert browser.closed_by == "asset-worker"
    assert browser.contexts[0].closed_by == "asset-worker"
    assert browser.contexts[0].pages[0].closed_by == "asset-worker"


def test_threaded_file_fetcher_close_releases_all_thread_private_browser_resources() -> (
    None
):
    runtime_context = _runtime_context_with_cdp_and_forbidden_shared_browser()
    browsers: list[_FakeBrowser] = []
    fetcher = browser_workflow._build_shared_browser_file_fetcher(
        browser_context_seed_getter=lambda: {"browser_user_agent": "UnitTestAgent/1.0"},
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=False,
        cdp_endpoint=TEST_CDP_ENDPOINT,
        thread_local=True,
    )

    created_fetchers = []

    def build_fetcher() -> None:
        inner_fetcher = fetcher._get_fetcher()
        created_fetchers.append(inner_fetcher)
        inner_fetcher._ensure_context()

    try:
        with mock.patch.dict(sys.modules, _fake_playwright_cdp_modules(browsers)):
            build_fetcher()
            worker = threading.Thread(target=build_fetcher, name="asset-worker")
            worker.start()
            worker.join()
    finally:
        fetcher.close()
        fetcher.close()

    runtime_context.new_browser_context.assert_not_called()
    assert len(created_fetchers) == 2
    assert len(browsers) == 2
    for browser in browsers:
        assert browser.closed is True
        assert len(browser.contexts) == 1
        assert browser.contexts[0].closed is True
        assert len(browser.contexts[0].pages) == 1
        assert browser.contexts[0].pages[0].closed is True
