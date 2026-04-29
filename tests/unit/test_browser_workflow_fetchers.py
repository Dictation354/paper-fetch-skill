from __future__ import annotations

import sys
import threading
import types
from unittest import mock

from paper_fetch.providers import browser_workflow
from paper_fetch.runtime import RuntimeContext


class _FakePage:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def goto(self, *_args, **_kwargs) -> None:
        return None


class _FakeRequestClient:
    def get(self, *_args, **_kwargs):  # pragma: no cover - request path is stubbed in tests
        raise AssertionError("unexpected request.get() call")


class _FakeContext:
    def __init__(self) -> None:
        self.closed = False
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


class _FakeBrowser:
    def __init__(self) -> None:
        self.closed = False
        self.contexts: list[_FakeContext] = []

    def new_context(self, **_kwargs) -> _FakeContext:
        context = _FakeContext()
        self.contexts.append(context)
        return context

    def close(self) -> None:
        self.closed = True


class _FakePlaywrightManager:
    def __init__(self) -> None:
        self.browser = _FakeBrowser()
        self.chromium = self
        self.stopped = False

    def launch(self, **_kwargs) -> _FakeBrowser:
        return self.browser

    def stop(self) -> None:
        self.stopped = True


class _FakeSyncPlaywrightSession:
    def __init__(self, managers: list[_FakePlaywrightManager]) -> None:
        self._managers = managers

    def start(self) -> _FakePlaywrightManager:
        manager = _FakePlaywrightManager()
        self._managers.append(manager)
        return manager


def _fake_playwright_modules(managers: list[_FakePlaywrightManager]) -> dict[str, types.ModuleType]:
    playwright_module = types.ModuleType("playwright")
    sync_api_module = types.ModuleType("playwright.sync_api")
    sync_api_module.sync_playwright = lambda: _FakeSyncPlaywrightSession(managers)
    playwright_module.sync_api = sync_api_module
    return {
        "playwright": playwright_module,
        "playwright.sync_api": sync_api_module,
    }


def _runtime_context_with_forbidden_shared_browser() -> RuntimeContext:
    context = RuntimeContext(env={})
    context.new_playwright_context = mock.Mock(side_effect=AssertionError("shared runtime browser should not be used"))
    return context


def test_threaded_image_fetcher_uses_thread_private_playwright_when_runtime_context_exists() -> None:
    runtime_context = _runtime_context_with_forbidden_shared_browser()
    managers: list[_FakePlaywrightManager] = []
    fetcher = browser_workflow._build_shared_playwright_image_fetcher(
        browser_context_seed_getter=lambda: {
            "browser_cookies": [{"name": "cf_clearance", "value": "seed", "domain": ".example.test", "path": "/"}],
            "browser_user_agent": "UnitTestAgent/1.0",
        },
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=False,
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
        with mock.patch.dict(sys.modules, _fake_playwright_modules(managers)):
            result = fetcher("https://example.test/figure.png", {"kind": "figure"})
    finally:
        fetcher.close()
        fetcher.close()

    assert result is not None
    runtime_context.new_playwright_context.assert_not_called()
    assert len(managers) == 1
    manager = managers[0]
    assert manager.stopped is True
    assert manager.browser.closed is True
    assert len(manager.browser.contexts) == 1
    assert manager.browser.contexts[0].closed is True
    assert len(manager.browser.contexts[0].pages) == 1
    assert manager.browser.contexts[0].pages[0].closed is True


def test_threaded_file_fetcher_uses_thread_private_playwright_when_runtime_context_exists() -> None:
    runtime_context = _runtime_context_with_forbidden_shared_browser()
    managers: list[_FakePlaywrightManager] = []
    fetcher = browser_workflow._build_shared_playwright_file_fetcher(
        browser_context_seed_getter=lambda: {
            "browser_cookies": [{"name": "cf_clearance", "value": "seed", "domain": ".example.test", "path": "/"}],
            "browser_user_agent": "UnitTestAgent/1.0",
        },
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=False,
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
        with mock.patch.dict(sys.modules, _fake_playwright_modules(managers)):
            result = fetcher("https://example.test/supplement.pdf", {"kind": "supplementary"})
    finally:
        fetcher.close()
        fetcher.close()

    assert result is not None
    runtime_context.new_playwright_context.assert_not_called()
    assert len(managers) == 1
    manager = managers[0]
    assert manager.stopped is True
    assert manager.browser.closed is True
    assert len(manager.browser.contexts) == 1
    assert manager.browser.contexts[0].closed is True
    assert len(manager.browser.contexts[0].pages) == 1
    assert manager.browser.contexts[0].pages[0].closed is True


def test_threaded_file_fetcher_close_releases_all_thread_private_playwright_resources() -> None:
    runtime_context = _runtime_context_with_forbidden_shared_browser()
    managers: list[_FakePlaywrightManager] = []
    fetcher = browser_workflow._build_shared_playwright_file_fetcher(
        browser_context_seed_getter=lambda: {"browser_user_agent": "UnitTestAgent/1.0"},
        seed_urls_getter=lambda: [],
        browser_user_agent="UnitTestAgent/1.0",
        runtime_context=runtime_context,
        use_runtime_shared_browser=False,
        thread_local=True,
    )

    created_fetchers = []

    def build_fetcher() -> None:
        inner_fetcher = fetcher._get_fetcher()
        created_fetchers.append(inner_fetcher)
        inner_fetcher._ensure_context()

    try:
        with mock.patch.dict(sys.modules, _fake_playwright_modules(managers)):
            build_fetcher()
            worker = threading.Thread(target=build_fetcher, name="asset-worker")
            worker.start()
            worker.join()
    finally:
        fetcher.close()
        fetcher.close()

    runtime_context.new_playwright_context.assert_not_called()
    assert len(created_fetchers) == 2
    assert len(managers) == 2
    for manager in managers:
        assert manager.stopped is True
        assert manager.browser.closed is True
        assert len(manager.browser.contexts) == 1
        assert manager.browser.contexts[0].closed is True
        assert len(manager.browser.contexts[0].pages) == 1
        assert manager.browser.contexts[0].pages[0].closed is True
