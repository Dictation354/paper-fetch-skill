from __future__ import annotations

import inspect
import io
import logging
from pathlib import Path
import socket
import threading
import time
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from paper_fetch import runtime as runtime_module
from paper_fetch import runtime_browser
from paper_fetch.runtime import RuntimeContext
from paper_fetch.runtime_browser import BrowserContextManager
from paper_fetch.workflow.batch_runner import run_batch


def test_browser_context_options_do_not_override_service_workers() -> None:
    options = runtime_browser.browser_context_options(accept_downloads=True)

    assert options == {
        "locale": runtime_browser.DEFAULT_BROWSER_LOCALE,
        "viewport": runtime_browser.DEFAULT_BROWSER_VIEWPORT,
        "accept_downloads": True,
    }
    assert "service_workers" not in options


def _write_stale_singletons(profile_dir: Path, *, pid: int = 99_999_999) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "SingletonLock").symlink_to(f"{socket.gethostname()}-{pid}")
    (profile_dir / "SingletonSocket").symlink_to(
        profile_dir / "missing-singleton-socket"
    )
    (profile_dir / "SingletonCookie").symlink_to("123456789")


def test_chromium_stale_singletons_are_detected_and_atomically_recovered(
    tmp_path,
) -> None:
    profile_dir = tmp_path / "profile"
    _write_stale_singletons(profile_dir)

    inspection = runtime_browser.inspect_chromium_singletons(profile_dir)
    diagnostic_dir = runtime_browser.recover_stale_chromium_singletons(
        profile_dir, inspection
    )

    assert inspection.state == "stale"
    assert inspection.reason == "singleton_pid_missing_and_socket_inactive"
    for name in runtime_browser.CHROMIUM_SINGLETON_FILENAMES:
        assert not (profile_dir / name).is_symlink()
        assert (diagnostic_dir / name).is_symlink()
    assert (diagnostic_dir / "recovery.json").is_file()


def test_chromium_recovery_rechecks_state_before_moving_files(tmp_path) -> None:
    profile_dir = tmp_path / "profile"
    _write_stale_singletons(profile_dir)
    inspection = runtime_browser.inspect_chromium_singletons(profile_dir)
    (profile_dir / "SingletonLock").unlink()
    (profile_dir / "SingletonLock").symlink_to("other-host-4242")

    with pytest.raises(RuntimeError, match="state changed"):
        runtime_browser.recover_stale_chromium_singletons(profile_dir, inspection)

    assert (profile_dir / "SingletonLock").is_symlink()
    assert (profile_dir / "SingletonSocket").is_symlink()
    assert (profile_dir / "SingletonCookie").is_symlink()


def test_chromium_active_profile_is_never_recovered(monkeypatch, tmp_path) -> None:
    profile_dir = tmp_path / "profile"
    _write_stale_singletons(profile_dir, pid=4242)
    monkeypatch.setattr(runtime_browser, "_process_exists", lambda _pid: True)
    monkeypatch.setattr(
        runtime_browser,
        "_process_cmdline",
        lambda _pid: f"/opt/chrome --user-data-dir={profile_dir}",
    )

    inspection = runtime_browser.inspect_chromium_singletons(profile_dir)

    assert inspection.state == "in_use"
    assert inspection.reason == "singleton_pid_active_for_profile"
    try:
        runtime_browser.recover_stale_chromium_singletons(profile_dir, inspection)
    except ValueError as exc:
        assert "confirmed stale" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("active profile must not be recovered")
    assert (profile_dir / "SingletonLock").is_symlink()


def test_chromium_reused_pid_for_other_process_is_not_recovered(
    monkeypatch, tmp_path
) -> None:
    profile_dir = tmp_path / "profile"
    _write_stale_singletons(profile_dir, pid=4242)
    monkeypatch.setattr(runtime_browser, "_process_exists", lambda _pid: True)
    monkeypatch.setattr(
        runtime_browser,
        "_process_cmdline",
        lambda _pid: "/usr/bin/unrelated-process",
    )

    inspection = runtime_browser.inspect_chromium_singletons(profile_dir)

    assert inspection.state == "in_use"
    assert inspection.reason == "singleton_pid_exists_for_other_process"
    assert (profile_dir / "SingletonLock").is_symlink()


def test_chromium_foreign_host_singleton_is_conservatively_in_use(
    tmp_path,
) -> None:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "SingletonLock").symlink_to("other-host-4242")
    (profile_dir / "SingletonSocket").symlink_to(profile_dir / "missing")
    (profile_dir / "SingletonCookie").symlink_to("123")

    inspection = runtime_browser.inspect_chromium_singletons(profile_dir)

    assert inspection.state == "in_use"
    assert inspection.reason == "singleton_lock_remote_host"


def test_managed_chrome_args_enforce_headless(monkeypatch, tmp_path) -> None:
    del monkeypatch

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
    del monkeypatch

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
        "_resolve_browser_binary",
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


def test_browser_manager_recovers_stale_singletons_before_launch(
    monkeypatch, tmp_path
) -> None:
    cdp_browser = _FakeCdpBrowser([])
    profile_dir = tmp_path / "profile"
    _write_stale_singletons(profile_dir)

    class _FakeProcess:
        stderr = None
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(
        runtime_browser,
        "_resolve_browser_binary",
        lambda _binary_path=None: "/tmp/chrome",
    )
    monkeypatch.setattr(runtime_browser, "_unused_tcp_port", lambda: 9333)
    monkeypatch.setattr(
        runtime_browser.subprocess,
        "Popen",
        lambda *_args, **_kwargs: _FakeProcess(),
    )
    monkeypatch.setattr(
        runtime_browser,
        "_wait_for_cdp_endpoint",
        lambda **_kwargs: "ws://127.0.0.1:9333/devtools/browser/managed",
    )
    monkeypatch.setattr(
        runtime_browser, "connect_browser_over_cdp", lambda _endpoint: cdp_browser
    )

    lifecycle = BrowserContextManager(profile_dir=profile_dir)
    lifecycle.new_context().close()
    recovery_paths = list(lifecycle._singleton_recovery_paths)
    lifecycle.close()

    assert len(recovery_paths) == 1
    assert (recovery_paths[0] / "recovery.json").is_file()


def test_browser_manager_recovers_new_stale_singletons_and_retries_once(
    monkeypatch, tmp_path
) -> None:
    profile_dir = tmp_path / "profile"
    attempts: list[int] = []

    monkeypatch.setattr(
        runtime_browser,
        "_resolve_browser_binary",
        lambda _binary_path=None: "/tmp/chrome",
    )

    lifecycle = BrowserContextManager(profile_dir=profile_dir)

    def launch(**_kwargs) -> str:
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            _write_stale_singletons(profile_dir)
            raise runtime_browser.ManagedBrowserError(
                "managed_chrome_exited_before_cdp",
                "Chrome exited.",
                stage="managed_chrome_startup",
            )
        return "ws://127.0.0.1:9333/devtools/browser/recovered"

    monkeypatch.setattr(lifecycle, "_launch_managed_chrome", launch)

    endpoint = lifecycle._ensure_managed_cdp_endpoint(headless=True)
    lifecycle.close()

    assert endpoint.endswith("/recovered")
    assert attempts == [1, 2]
    assert len(lifecycle._singleton_recovery_paths) == 1


def test_managed_chrome_startup_failure_keeps_redacted_bounded_diagnostic(
    monkeypatch, tmp_path
) -> None:
    profile_dir = tmp_path / "profile"

    class _FakeProcess:
        def __init__(self) -> None:
            self.stderr = io.BytesIO(
                b"x" * (runtime_browser.DEFAULT_BROWSER_STDERR_TAIL_BYTES + 512)
                + b"\ntoken=super-secret\nlast startup failure\n"
            )
            self.returncode = 12

        def poll(self):
            return self.returncode

        def terminate(self) -> None:
            pass

        def wait(self, timeout=None):
            return self.returncode

        def kill(self) -> None:
            pass

    monkeypatch.setattr(
        runtime_browser,
        "_resolve_browser_binary",
        lambda _binary_path=None: "/tmp/chrome",
    )
    monkeypatch.setattr(runtime_browser, "_unused_tcp_port", lambda: 9333)
    monkeypatch.setattr(
        runtime_browser.subprocess,
        "Popen",
        lambda *_args, **_kwargs: _FakeProcess(),
    )

    lifecycle = BrowserContextManager(profile_dir=profile_dir)
    try:
        lifecycle.new_context()
    except runtime_browser.ManagedBrowserError as exc:
        error = exc
    else:  # pragma: no cover
        raise AssertionError("expected managed Chrome startup failure")

    assert error.code == "managed_chrome_exited_before_cdp"
    assert error.stage == "managed_chrome_startup"
    assert error.details["exit_code"] == 12
    assert "super-secret" not in str(error.details["stderr_summary"])
    assert "[REDACTED]" in str(error.details["stderr_summary"])
    assert len(str(error.details["stderr_summary"])) <= (
        runtime_browser.DEFAULT_BROWSER_ERROR_SUMMARY_CHARS
    )
    diagnostic_path = Path(str(error.details["diagnostic_path"]))
    assert (diagnostic_path / "diagnostic.json").is_file()
    stderr_log = (diagnostic_path / "chrome-stderr.log").read_text()
    assert "super-secret" not in stderr_log
    assert len(stderr_log.encode("utf-8")) <= (
        runtime_browser.DEFAULT_BROWSER_STDERR_TAIL_BYTES
    )


def test_wait_for_cdp_endpoint_has_distinct_exit_and_timeout_codes() -> None:
    exited = SimpleNamespace(poll=lambda: 17, returncode=17)
    try:
        runtime_browser._wait_for_cdp_endpoint(
            process=exited,
            port=9333,
            timeout_seconds=1,
        )
    except runtime_browser.ManagedBrowserError as exc:
        assert exc.code == "managed_chrome_exited_before_cdp"
        assert exc.details["exit_code"] == 17
    else:  # pragma: no cover
        raise AssertionError("expected early Chrome exit")

    running = SimpleNamespace(poll=lambda: None, returncode=None)
    try:
        runtime_browser._wait_for_cdp_endpoint(
            process=running,
            port=9333,
            timeout_seconds=0,
        )
    except runtime_browser.ManagedBrowserError as exc:
        assert exc.code == "managed_chrome_cdp_timeout"
    else:  # pragma: no cover
        raise AssertionError("expected CDP timeout")


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
        "_resolve_browser_binary",
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
        "_resolve_browser_binary",
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
    except runtime_browser.ManagedBrowserError as exc:
        assert str(exc) == "connect failed"
        assert exc.code == "cdp_connect_failed"
    else:  # pragma: no cover - assertion reports the unexpected success path
        raise AssertionError("expected CDP connect failure")
    profile_lock = runtime_browser._profile_lock_for_dir(profile_dir)
    profile_lock.acquire(timeout=0)
    profile_lock.release()

    assert process.terminated is True


def test_browser_manager_reports_context_creation_stage(monkeypatch) -> None:
    class _ContextFailureBrowser(_FakeCdpBrowser):
        def new_context(self, **kwargs: Any):
            del kwargs
            raise RuntimeError("context failed")

    monkeypatch.setattr(
        runtime_browser,
        "connect_browser_over_cdp",
        lambda _endpoint: _ContextFailureBrowser([]),
    )
    lifecycle = BrowserContextManager(
        cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
        external_new_context=True,
    )

    try:
        lifecycle.new_context()
    except runtime_browser.ManagedBrowserError as exc:
        assert exc.code == "browser_context_create_failed"
        assert exc.stage == "browser_context_create"
    else:  # pragma: no cover
        raise AssertionError("expected browser context creation failure")


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
        "_resolve_browser_binary",
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


def test_runtime_context_passes_explicit_cdp_endpoint_to_browser_manager(
    monkeypatch,
) -> None:
    cdp_context = _FakeCdpContext()
    cdp_browser = _FakeCdpBrowser([cdp_context])
    endpoints: list[str] = []

    def connect(endpoint: str) -> _FakeCdpBrowser:
        endpoints.append(endpoint)
        return cdp_browser

    monkeypatch.setattr(runtime_browser, "connect_browser_over_cdp", connect)
    context = RuntimeContext(env={})

    try:
        borrowed = context.new_browser_context_for_config(
            headless=True,
            cdp_endpoint="ws://127.0.0.1:9222/devtools/browser/test",
        )
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


def test_batch_scope_retains_idle_browser_manager_between_items(
    monkeypatch, tmp_path
) -> None:
    created: list[Any] = []

    class FakeLifecycle:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = dict(kwargs)
            self.close_count = 0
            created.append(self)

        def new_context(self, **kwargs: Any):
            return self

        def close(self) -> None:
            self.close_count += 1

    monkeypatch.setattr(runtime_module, "BrowserContextManager", FakeLifecycle)
    profile_dir = tmp_path / "wiley-profile"

    with runtime_module.retain_shared_browser_managers():
        first_runtime = RuntimeContext(env={})
        first = first_runtime.new_browser_context_for_config(profile_dir=profile_dir)
        first_runtime.close()
        retained = runtime_module.dump_shared_browser_managers()

        second_runtime = RuntimeContext(env={})
        second = second_runtime.new_browser_context_for_config(profile_dir=profile_dir)
        second_runtime.close()

        assert first is second
        assert retained[0]["ref_count"] == 0
        assert retained[0]["retained_by_batch_scope"] is True
        assert created[0].close_count == 0

    assert created[0].close_count == 1


def test_four_worker_batch_reuses_one_manager_across_fifty_contexts_and_gaps(
    monkeypatch, tmp_path
) -> None:
    created: list[Any] = []

    class FakeContext:
        def close(self) -> None:
            pass

    class FakeLifecycle:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = dict(kwargs)
            self.context_count = 0
            self.close_count = 0
            self.lock = threading.Lock()
            created.append(self)

        def new_context(self, **kwargs: Any):
            del kwargs
            with self.lock:
                self.context_count += 1
            return FakeContext()

        def close(self) -> None:
            self.close_count += 1

    monkeypatch.setattr(runtime_module, "BrowserContextManager", FakeLifecycle)
    profile_dir = tmp_path / "wiley-profile"

    def worker(index: int) -> int:
        context = RuntimeContext(env={})
        browser_context = context.new_browser_context_for_config(
            profile_dir=profile_dir
        )
        browser_context.close()
        context.close()
        if index % 7 == 0:
            time.sleep(0.005)
        return index

    result = run_batch(list(range(50)), worker, max_workers=4)

    assert [item.value for item in result.results] == list(range(50))
    assert len(created) == 1
    assert created[0].context_count == 50
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
