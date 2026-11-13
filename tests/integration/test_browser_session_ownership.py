"""Real-thread contracts for the request-local browser session owner."""

from dataclasses import replace


from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading

import pytest

from paper_fetch.http import RequestCancelledError
from paper_fetch.providers.browser_runtime.types import (
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)
from paper_fetch.runtime import RuntimeContext


def install_backend(monkeypatch, events, *, close_started=None, finish_close=None):
    from paper_fetch.providers.browser_runtime import api

    class Manager:
        def __init__(self, config):
            self.config = config
            self.context = object()
            self.owner = threading.get_ident()
            self.diagnostics = {"provider": config.provider}
            events.append(("create", config.provider, self.owner))

        def new_context(self):
            assert threading.get_ident() == self.owner
            return self.context

        def refresh(self):
            events.append(("refresh", self.config.provider, self.owner))

        def close(self):
            assert threading.get_ident() == self.owner
            events.append(("manager", self.config.provider, self.owner))
            if close_started is not None:
                close_started.set()
                assert finish_close.wait(5)

    monkeypatch.setattr(
        api,
        "_backend",
        lambda _: SimpleNamespace(
            create_manager=lambda config, **kwargs: Manager(config)
        ),
    )


def config_for(tmp_path, provider="wiley"):
    return BrowserRuntimeConfig(
        provider=provider,
        doi="10.1234/example",
        artifact_dir=tmp_path,
        profile_dir=tmp_path / provider,
        headless=True,
        user_agent=None,
    )


def test_session_reuse_conflicts_and_publisher_switch_close_cached_pages(
    monkeypatch, tmp_path
):
    events = []
    install_backend(monkeypatch, events)
    with RuntimeContext(env={}) as runtime:
        config = config_for(tmp_path)
        first = runtime.new_browser_context_for_runtime_config(config)
        assert runtime.new_browser_context_for_runtime_config(config) is first
        assert runtime.browser_profile_diagnostics(first) == {"provider": "wiley"}
        runtime.refresh_browser_profiles()
        runtime.session_cache[("page",)] = SimpleNamespace(
            context=first,
            close=lambda: events.append(("page", "wiley", threading.get_ident())),
        )
        with pytest.raises(BrowserRuntimeFailure, match="belongs to wiley"):
            runtime.new_browser_context_for_runtime_config(
                replace(config, provider="science")
            )
        with pytest.raises(RuntimeError, match="Conflicting browser executable"):
            runtime.new_browser_context_for_runtime_config(
                replace(config, binary_path="different")
            )
        second = runtime.new_browser_context_for_runtime_config(
            config_for(tmp_path, "science")
        )
        assert second is not first
        assert not runtime.session_cache
        labels = [(kind, provider) for kind, provider, _ in events]
        assert labels == [
            ("create", "wiley"),
            ("refresh", "wiley"),
            ("page", "wiley"),
            ("manager", "wiley"),
            ("create", "science"),
        ]


def test_batch_children_own_sessions_and_borrow_only_transport(monkeypatch, tmp_path):
    events = []
    install_backend(monkeypatch, events)
    with RuntimeContext(env={}) as parent:
        first = parent.new_request_context()
        second = parent.new_request_context()
        try:
            assert first.transport is second.transport is parent.transport
            first_context = first.new_browser_context_for_runtime_config(
                config_for(tmp_path)
            )
            second_context = second.new_browser_context_for_runtime_config(
                config_for(tmp_path)
            )
            assert first_context is not second_context
            assert first._browser_sessions is not second._browser_sessions
            assert not parent._camoufox_browser_managers
            first.close()
            assert (
                second.new_browser_context_for_runtime_config(config_for(tmp_path))
                is second_context
            )
        finally:
            first.close()
            second.close()
    assert [kind for kind, *_ in events] == ["create", "create", "manager", "manager"]


def test_foreign_close_fences_and_retains_handles_until_owner_cleanup(
    monkeypatch, tmp_path
):
    events = []
    ready, release = threading.Event(), threading.Event()
    close_started, finish_close = threading.Event(), threading.Event()
    install_backend(
        monkeypatch, events, close_started=close_started, finish_close=finish_close
    )
    runtime = RuntimeContext(env={})
    transport_close = runtime.transport.close

    def close_transport():
        assert not runtime.session_cache and not runtime.parse_cache
        events.append(("transport", "", threading.get_ident()))
        transport_close()

    monkeypatch.setattr(runtime.transport, "close", close_transport)
    runtime.parse_cache[("parse",)] = "cached"

    def worker():
        context = runtime.new_browser_context_for_runtime_config(config_for(tmp_path))
        runtime.session_cache[("page",)] = SimpleNamespace(
            context=context,
            close=lambda: events.append(("page", "wiley", threading.get_ident())),
        )
        ready.set()
        assert release.wait(5)
        runtime.close_camoufox_for_current_thread()
        runtime.close()
        return threading.get_ident()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(worker)
        try:
            assert ready.wait(5)
            runtime.close()
            assert runtime._camoufox_browser_managers and runtime.parse_cache
            with pytest.raises(RequestCancelledError):
                runtime.commit_guard()
            release.set()
            assert close_started.wait(5)
            runtime.close()
            assert runtime._camoufox_browser_managers
            assert not any(kind == "transport" for kind, *_ in events)
        finally:
            release.set()
            finish_close.set()
        owner = future.result(timeout=5)
    runtime.close()
    assert [kind for kind, *_ in events] == ["create", "page", "manager", "transport"]
    assert all(thread == owner for _, _, thread in events)
