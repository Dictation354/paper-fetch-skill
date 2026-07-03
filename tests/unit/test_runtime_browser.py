from __future__ import annotations

import inspect
import logging
import sys
from types import SimpleNamespace
from typing import Any
from unittest import mock

from paper_fetch import runtime as runtime_module
from paper_fetch import runtime_browser
from paper_fetch.runtime import RuntimeContext
from paper_fetch.runtime_browser import BrowserContextManager


def test_managed_chrome_args_enforce_headless_when_cloakbrowser_omits_flag(
    monkeypatch, tmp_path
) -> None:
    def build_args(_fingerprint: bool, args: list[str], **_kwargs: Any) -> list[str]:
        return ["--no-sandbox", *args, "--lang=en-US"]

    monkeypatch.setitem(
        sys.modules, "cloakbrowser", SimpleNamespace(build_args=build_args)
    )

    args = runtime_browser._build_managed_chrome_args(
        headless=True,
        profile_dir=tmp_path / "profile",
        port=9333,
    )

    assert "--headless=new" in args
    assert f"--user-data-dir={tmp_path / 'profile'}" in args
    assert "--remote-debugging-port=9333" in args


def test_managed_chrome_args_keep_headed_mode_when_requested(
    monkeypatch, tmp_path
) -> None:
    def build_args(_fingerprint: bool, args: list[str], **_kwargs: Any) -> list[str]:
        return ["--no-sandbox", *args, "--lang=en-US"]

    monkeypatch.setitem(
        sys.modules, "cloakbrowser", SimpleNamespace(build_args=build_args)
    )

    args = runtime_browser._build_managed_chrome_args(
        headless=False,
        profile_dir=tmp_path / "profile",
        port=9333,
    )

    assert "--headless=new" not in args


class _FakeCdpContext:
    def __init__(self) -> None:
        self.close_count = 0
        self.pages: list[SimpleNamespace] = []
        self.cookies: list[dict[str, Any]] = []

    def new_page(self) -> SimpleNamespace:
        page = SimpleNamespace(closed=False)
        self.pages.append(page)
        return page

    def add_cookies(self, cookies: list[dict[str, Any]]) -> None:
        self.cookies.extend([dict(cookie) for cookie in cookies])

    def close(self) -> None:
        self.close_count += 1


class _FakeCdpBrowser:
    def __init__(self, contexts: list[_FakeCdpContext] | None = None) -> None:
        self.contexts = list(contexts or [])
        self.new_context_kwargs: list[dict[str, Any]] = []
        self.close_count = 0

    def new_context(self, **kwargs: Any) -> _FakeCdpContext:
        context = _FakeCdpContext()
        self.contexts.append(context)
        self.new_context_kwargs.append(dict(kwargs))
        return context

    def close(self) -> None:
        self.close_count += 1


def test_browser_manager_auto_starts_managed_cdp_browser(monkeypatch, tmp_path) -> None:
    cdp_browser = _FakeCdpBrowser([_FakeCdpContext()])
    endpoints: list[str] = []
    popen_calls: list[list[str]] = []

    class _FakeProcess:
        def __init__(self) -> None:
            self.returncode = None
            self.terminated = False
            self.killed = False

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

        def kill(self) -> None:
            self.killed = True
            self.returncode = -9

    process = _FakeProcess()

    def popen(command: list[str], **_kwargs: Any) -> _FakeProcess:
        popen_calls.append(list(command))
        return process

    def connect(endpoint: str) -> _FakeCdpBrowser:
        endpoints.append(endpoint)
        return cdp_browser

    monkeypatch.setattr(
        runtime_browser,
        "_resolve_cloakbrowser_binary",
        lambda _binary_path=None: "/tmp/chrome",
    )
    monkeypatch.setattr(runtime_browser, "_unused_tcp_port", lambda: 9333)
    monkeypatch.setattr(runtime_browser.subprocess, "Popen", popen)
    monkeypatch.setattr(
        runtime_browser,
        "_wait_for_cdp_endpoint",
        lambda **_kwargs: "ws://127.0.0.1:9333/devtools/browser/managed",
    )
    monkeypatch.setattr(runtime_browser, "connect_browser_over_cdp", connect)

    profile_dir = tmp_path / "profile"
    lifecycle = BrowserContextManager(profile_dir=profile_dir)
    context = lifecycle.new_context(headless=True, locale="en-US")
    context.close()
    lifecycle.close()
    profile_lock = runtime_browser._profile_lock_for_dir(profile_dir)
    profile_lock.acquire(timeout=0)
    profile_lock.release()

    assert endpoints == ["ws://127.0.0.1:9333/devtools/browser/managed"]
    assert cdp_browser.new_context_kwargs == [{"locale": "en-US"}]
    assert popen_calls[0][0] == "/tmp/chrome"
    assert f"--user-data-dir={tmp_path / 'profile'}" in popen_calls[0]
    assert "--remote-debugging-port=9333" in popen_calls[0]
    assert process.terminated is True
    assert cdp_browser.close_count == 1


def test_browser_manager_restarts_managed_browser_when_headless_changes(
    monkeypatch, tmp_path
) -> None:
    cdp_browsers = [_FakeCdpBrowser([]), _FakeCdpBrowser([])]
    endpoints: list[str] = []
    popen_calls: list[list[str]] = []
    processes: list[Any] = []
    ports = iter([9333, 9444])

    class _FakeProcess:
        def __init__(self) -> None:
            self.returncode = None
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    def popen(command: list[str], **_kwargs: Any) -> _FakeProcess:
        process = _FakeProcess()
        processes.append(process)
        popen_calls.append(list(command))
        return process

    def build_args(*, headless: bool, profile_dir, port: int) -> list[str]:
        return [
            f"--headless={str(headless).lower()}",
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={port}",
        ]

    def connect(endpoint: str) -> _FakeCdpBrowser:
        endpoints.append(endpoint)
        return cdp_browsers[len(endpoints) - 1]

    monkeypatch.setattr(
        runtime_browser,
        "_resolve_cloakbrowser_binary",
        lambda _binary_path=None: "/tmp/chrome",
    )
    monkeypatch.setattr(runtime_browser, "_unused_tcp_port", lambda: next(ports))
    monkeypatch.setattr(runtime_browser, "_build_managed_chrome_args", build_args)
    monkeypatch.setattr(runtime_browser.subprocess, "Popen", popen)
    monkeypatch.setattr(
        runtime_browser,
        "_wait_for_cdp_endpoint",
        lambda *, port, **_kwargs: f"ws://127.0.0.1:{port}/devtools/browser/managed",
    )
    monkeypatch.setattr(runtime_browser, "connect_browser_over_cdp", connect)

    lifecycle = BrowserContextManager(profile_dir=tmp_path / "profile")
    lifecycle.new_context(headless=True).close()
    lifecycle.new_context(headless=False).close()
    lifecycle.close()

    assert endpoints == [
        "ws://127.0.0.1:9333/devtools/browser/managed",
        "ws://127.0.0.1:9444/devtools/browser/managed",
    ]
    assert popen_calls[0][1] == "--headless=true"
    assert popen_calls[1][1] == "--headless=false"
    assert cdp_browsers[0].close_count == 1
    assert cdp_browsers[1].close_count == 1
    assert [process.terminated for process in processes] == [True, True]


def test_browser_manager_terminates_managed_browser_when_cdp_connect_fails(
    monkeypatch, tmp_path
) -> None:
    class _FakeProcess:
        def __init__(self) -> None:
            self.returncode = None
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    process = _FakeProcess()

    monkeypatch.setattr(
        runtime_browser,
        "_resolve_cloakbrowser_binary",
        lambda _binary_path=None: "/tmp/chrome",
    )
    monkeypatch.setattr(runtime_browser, "_unused_tcp_port", lambda: 9333)
    monkeypatch.setattr(
        runtime_browser.subprocess, "Popen", lambda *_args, **_kwargs: process
    )
    monkeypatch.setattr(
        runtime_browser,
        "_wait_for_cdp_endpoint",
        lambda **_kwargs: "ws://127.0.0.1:9333/devtools/browser/managed",
    )
    monkeypatch.setattr(
        runtime_browser,
        "connect_browser_over_cdp",
        mock.Mock(side_effect=RuntimeError("connect failed")),
    )

    profile_dir = tmp_path / "profile"
    lifecycle = BrowserContextManager(profile_dir=profile_dir)
    try:
        lifecycle.new_context(headless=True)
    except RuntimeError as exc:
        assert str(exc) == "connect failed"
    else:  # pragma: no cover - assertion reports the unexpected success path
        raise AssertionError("expected CDP connect failure")
    profile_lock = runtime_browser._profile_lock_for_dir(profile_dir)
    profile_lock.acquire(timeout=0)
    profile_lock.release()

    assert process.terminated is True


def test_browser_manager_profile_lock_timeout_reports_error(
    monkeypatch, tmp_path
) -> None:
    class _BlockingLock:
        def acquire(self, *, timeout: float) -> None:
            assert timeout == 0
            raise runtime_browser.Timeout("locked")

        def release(self) -> None:  # pragma: no cover - should not be reached
            raise AssertionError(
                "profile lock should not be released when acquire fails"
            )

    monkeypatch.setattr(
        runtime_browser,
        "_resolve_cloakbrowser_binary",
        lambda _binary_path=None: "/tmp/chrome",
    )
    monkeypatch.setattr(
        runtime_browser, "_profile_lock_for_dir", lambda _profile_dir: _BlockingLock()
    )
    popen = mock.Mock()
    monkeypatch.setattr(runtime_browser.subprocess, "Popen", popen)

    profile_dir = tmp_path / "profile"
    lifecycle = BrowserContextManager(
        profile_dir=profile_dir,
        profile_lock_timeout_seconds=0,
    )
    try:
        lifecycle.new_context(headless=True)
    except RuntimeError as exc:
        assert "Timed out waiting for managed Chrome profile lock" in str(exc)
        assert str(profile_dir / runtime_browser.PROFILE_LOCK_FILENAME) in str(exc)
    else:  # pragma: no cover - assertion reports the unexpected success path
        raise AssertionError("expected profile lock timeout")

    popen.assert_not_called()


def test_browser_manager_reuses_existing_cdp_context_without_closing_it(
    monkeypatch,
) -> None:
    cdp_context = _FakeCdpContext()
    cdp_browser = _FakeCdpBrowser([cdp_context])
    endpoints: list[str] = []

    def connect(endpoint: str) -> _FakeCdpBrowser:
        endpoints.append(endpoint)
        return cdp_browser

    monkeypatch.setattr(runtime_browser, "connect_browser_over_cdp", connect)
    lifecycle = BrowserContextManager(
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test"
    )

    context = lifecycle.new_context(headless=True, locale="en-US")
    page = context.new_page()
    context.close()
    second_context = lifecycle.new_context(headless=False)
    second_page = second_context.new_page()
    second_context.close()
    lifecycle.close()

    assert endpoints == [
        "ws://127.0.0.1:9222/devtools/browser/test",
        "ws://127.0.0.1:9222/devtools/browser/test",
    ]
    assert page in cdp_context.pages
    assert second_page in cdp_context.pages
    assert cdp_browser.new_context_kwargs == []
    assert cdp_context.close_count == 0
    assert cdp_browser.close_count == 2


def test_browser_manager_injects_storage_state_cookies_into_external_context(
    monkeypatch,
) -> None:
    cdp_context = _FakeCdpContext()
    cdp_browser = _FakeCdpBrowser([cdp_context])
    monkeypatch.setattr(
        runtime_browser,
        "connect_browser_over_cdp",
        lambda _endpoint: cdp_browser,
    )
    lifecycle = BrowserContextManager(
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test"
    )

    context = lifecycle.new_context(
        headless=True,
        storage_state={
            "cookies": [
                {
                    "name": "session",
                    "value": "seed",
                    "domain": ".example.test",
                    "path": "/",
                }
            ]
        },
    )
    context.close()
    lifecycle.close()

    assert cdp_context.cookies == [
        {
            "name": "session",
            "value": "seed",
            "domain": ".example.test",
            "path": "/",
        }
    ]
    assert cdp_context.close_count == 0
    assert cdp_browser.new_context_kwargs == []


def test_browser_manager_logs_ignored_external_context_options(
    monkeypatch, caplog
) -> None:
    cdp_context = _FakeCdpContext()
    cdp_browser = _FakeCdpBrowser([cdp_context])
    monkeypatch.setattr(
        runtime_browser,
        "connect_browser_over_cdp",
        lambda _endpoint: cdp_browser,
    )
    caplog.set_level(logging.DEBUG, logger="paper_fetch.runtime_browser")
    lifecycle = BrowserContextManager(
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test"
    )

    context = lifecycle.new_context(
        headless=True,
        user_agent="Mozilla/5.0 ignored",
        storage_state="/tmp/ignored-state.json",
    )
    context.close()
    lifecycle.close()

    assert "cdp_external_context_ignored_options" in caplog.text
    assert "keys=user_agent" in caplog.text


def test_browser_manager_creates_owned_context_when_cdp_browser_has_no_contexts(
    monkeypatch,
) -> None:
    cdp_browser = _FakeCdpBrowser([])
    monkeypatch.setattr(
        runtime_browser,
        "connect_browser_over_cdp",
        lambda _endpoint: cdp_browser,
    )
    lifecycle = BrowserContextManager(
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test"
    )

    context = lifecycle.new_context(headless=True, locale="en-US")
    context.close()
    lifecycle.close()

    assert len(cdp_browser.contexts) == 1
    assert cdp_browser.new_context_kwargs == [{"locale": "en-US"}]
    assert cdp_browser.contexts[0].close_count == 1
    assert cdp_browser.close_count == 1


def test_browser_manager_external_new_context_does_not_borrow_existing_context(
    monkeypatch,
) -> None:
    existing_context = _FakeCdpContext()
    cdp_browser = _FakeCdpBrowser([existing_context])
    monkeypatch.setattr(
        runtime_browser,
        "connect_browser_over_cdp",
        lambda _endpoint: cdp_browser,
    )
    lifecycle = BrowserContextManager(
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
        external_new_context=True,
    )

    context = lifecycle.new_context(headless=True, locale="en-US")
    diagnostics = context._paper_fetch_external_cdp_diagnostics
    context.close()
    lifecycle.close()

    assert len(cdp_browser.contexts) == 2
    assert existing_context.close_count == 0
    assert cdp_browser.new_context_kwargs == [{"locale": "en-US"}]
    assert diagnostics["borrowed_existing_context"] is False


def test_runtime_context_passes_env_cdp_endpoint_to_browser_manager(
    monkeypatch,
) -> None:
    cdp_context = _FakeCdpContext()
    cdp_browser = _FakeCdpBrowser([cdp_context])
    endpoints: list[str] = []

    def connect(endpoint: str) -> _FakeCdpBrowser:
        endpoints.append(endpoint)
        return cdp_browser

    monkeypatch.setattr(runtime_browser, "connect_browser_over_cdp", connect)
    context = RuntimeContext(
        env={"CLOAKBROWSER_CDP_ENDPOINT": "ws://127.0.0.1:9222/devtools/browser/test"}
    )

    try:
        borrowed = context.new_browser_context(headless=True)
        borrowed.close()
    finally:
        context.close()

    assert endpoints == ["ws://127.0.0.1:9222/devtools/browser/test"]
    assert cdp_context.close_count == 0
    assert cdp_browser.close_count == 1


def test_runtime_context_caches_browser_managers_by_runtime_config(
    monkeypatch, tmp_path
) -> None:
    created: list[dict[str, Any]] = []

    class FakeLifecycle:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = dict(kwargs)
            self.close_count = 0
            created.append(self.kwargs)

        def new_context(
            self, **kwargs: Any
        ) -> tuple[str, dict[str, Any], dict[str, Any]]:
            return "context", self.kwargs, dict(kwargs)

        def close(self) -> None:
            self.close_count += 1

    monkeypatch.setattr(runtime_module, "BrowserContextManager", FakeLifecycle)
    context = RuntimeContext(env={})

    first = context.new_browser_context_for_config(
        headless=True,
        profile_dir=tmp_path / "science-profile",
        locale="en-US",
    )
    second = context.new_browser_context_for_config(
        headless=False,
        profile_dir=tmp_path / "science-profile",
        viewport={"width": 800},
    )
    third = context.new_browser_context_for_config(
        headless=True,
        profile_dir=tmp_path / "pnas-profile",
    )
    context.close()

    assert first[1] is second[1]
    assert first[1]["profile_dir"] == tmp_path / "science-profile"
    assert third[1]["profile_dir"] == tmp_path / "pnas-profile"
    assert len(created) == 2


def test_runtime_context_dump_shared_browser_managers(monkeypatch, tmp_path) -> None:
    class FakeLifecycle:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = dict(kwargs)

        def new_context(
            self, **kwargs: Any
        ) -> tuple[str, dict[str, Any], dict[str, Any]]:
            return "context", self.kwargs, dict(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(runtime_module, "BrowserContextManager", FakeLifecycle)
    context = RuntimeContext(env={})
    context.new_browser_context_for_config(
        headless=True,
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
        external_new_context=True,
        profile_dir=tmp_path / "science-profile",
    )

    dump = runtime_module.dump_shared_browser_managers()
    context.close()

    assert any(item["ref_count"] == 1 for item in dump)
    assert any(item["external_cdp"] for item in dump)
    assert any(item["external_new_context"] for item in dump)


def test_runtime_context_shares_browser_managers_across_runtime_instances(
    monkeypatch, tmp_path
) -> None:
    created: list[Any] = []

    class FakeLifecycle:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = dict(kwargs)
            self.close_count = 0
            created.append(self)

        def new_context(
            self, **kwargs: Any
        ) -> tuple[str, dict[str, Any], dict[str, Any]]:
            return "context", self.kwargs, dict(kwargs)

        def close(self) -> None:
            self.close_count += 1

    monkeypatch.setattr(runtime_module, "BrowserContextManager", FakeLifecycle)
    profile_dir = tmp_path / "science-profile"
    first_runtime = RuntimeContext(env={})
    second_runtime = RuntimeContext(env={})

    first = first_runtime.new_browser_context_for_config(
        headless=True,
        profile_dir=profile_dir,
        locale="en-US",
    )
    second = second_runtime.new_browser_context_for_config(
        headless=True,
        profile_dir=profile_dir,
        locale="en-US",
    )
    first_runtime.close()
    third = second_runtime.new_browser_context_for_config(
        headless=True,
        profile_dir=profile_dir,
        viewport={"width": 800},
    )
    second_runtime.close()

    assert first[1] is second[1] is third[1]
    assert len(created) == 1
    assert created[0].close_count == 1


def test_runtime_context_recommended_browser_context_entrypoint() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeLifecycle:
        def browser(self, **kwargs: Any) -> str:
            calls.append(("browser", dict(kwargs)))
            return "browser"

        def new_context(self, **kwargs: Any) -> str:
            calls.append(("new_context", dict(kwargs)))
            return "context"

        def close(self) -> None:
            calls.append(("close", {}))

    context = RuntimeContext(env={})
    context._browser_context_manager = FakeLifecycle()  # type: ignore[assignment]

    assert context.new_browser_context(headless=True, locale="en-US") == "context"
    assert (
        context.new_browser_context(headless=True, viewport={"width": 800}) == "context"
    )
    context.close()

    assert calls == [
        ("new_context", {"headless": True, "locale": "en-US"}),
        ("new_context", {"headless": True, "viewport": {"width": 800}}),
        ("close", {}),
    ]


def test_sync_playwright_usage_is_confined_to_cdp_connector() -> None:
    source = inspect.getsource(runtime_browser.connect_browser_over_cdp)

    assert "sync_playwright(" in source
    assert "connect_over_cdp" in source
