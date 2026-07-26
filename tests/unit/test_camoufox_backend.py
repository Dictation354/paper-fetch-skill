from __future__ import annotations

from types import SimpleNamespace
import threading
from unittest import mock

import pytest

from paper_fetch.config import (
    BROWSER_BACKEND_ENV_VAR,
    BROWSER_BINARY_PATH_ENV_VAR,
    BROWSER_HEADLESS_ENV_VAR,
    BROWSER_PROFILE_DIR_ENV_VAR,
    BROWSER_TIMEOUT_MS_ENV_VAR,
    BROWSER_USER_AGENT_ENV_VAR,
    XDG_DATA_HOME_ENV_VAR,
)
from paper_fetch.providers import _playwright_browser, browser_runtime
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_runtime.backends.camoufox import (
    CamoufoxBackend,
    _dependency_details,
)
from paper_fetch.providers.browser_runtime.camoufox_manager import (
    CamoufoxBrowserManager,
    _launch_executable_path,
)
from paper_fetch.providers.browser_runtime.context import context_options_for_config
from paper_fetch.providers.browser_runtime import context as browser_runtime_context
from paper_fetch.providers.browser_runtime.types import BrowserRuntimeConfig
from paper_fetch.runtime import RuntimeContext


def test_backend_selection_defaults_to_camoufox_and_accepts_explicit_value() -> None:
    assert browser_runtime.selected_browser_runtime_backend({}).name == "camoufox"
    assert (
        browser_runtime.selected_browser_runtime_backend(
            {BROWSER_BACKEND_ENV_VAR: "CAMOUFOX"}
        ).name
        == "camoufox"
    )


def test_browser_runtime_config_requires_explicit_backend(tmp_path) -> None:
    with pytest.raises(TypeError, match="backend"):
        BrowserRuntimeConfig(  # type: ignore[call-arg]
            provider="ieee",
            doi="10.1109/example",
            artifact_dir=tmp_path,
            headless=True,
            user_agent=None,
        )


def test_camoufox_context_failure_closes_at_backend_boundary(
    monkeypatch, tmp_path
) -> None:
    camoufox_manager = mock.Mock()
    camoufox_manager.return_value.new_context.side_effect = RuntimeError(
        "camoufox failed"
    )
    monkeypatch.setattr(
        browser_runtime_context, "CamoufoxBrowserManager", camoufox_manager
    )
    config = BrowserRuntimeConfig(
        provider="ieee",
        doi="10.1109/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        backend="camoufox",
    )

    with pytest.raises(RuntimeError, match="camoufox failed"):
        browser_runtime_context.open_browser_context(config)

    camoufox_manager.assert_called_once()


def test_invalid_backend_is_strict() -> None:
    with pytest.raises(ProviderFailure, match=BROWSER_BACKEND_ENV_VAR):
        browser_runtime.load_runtime_config(
            {BROWSER_BACKEND_ENV_VAR: "unknown"},
            provider="wiley",
            doi="10.1000/example",
        )


def test_camoufox_config_uses_generic_settings_and_separate_profile(tmp_path) -> None:
    executable = tmp_path / "camoufox"
    executable.write_text("runtime", encoding="utf-8")
    executable.chmod(0o755)
    env = {
        BROWSER_BACKEND_ENV_VAR: "camoufox",
        BROWSER_BINARY_PATH_ENV_VAR: str(executable),
        BROWSER_HEADLESS_ENV_VAR: "false",
        BROWSER_TIMEOUT_MS_ENV_VAR: "45678",
        BROWSER_USER_AGENT_ENV_VAR: "Chrome override must be ignored",
        XDG_DATA_HOME_ENV_VAR: str(tmp_path / "xdg"),
    }

    config = browser_runtime.load_runtime_config(
        env,
        provider="annualreviews",
        doi="10.1146/example",
    )

    assert config.backend == "camoufox"
    assert config.binary_path == str(executable)
    assert config.headless is False
    assert config.timeout_ms == 45678
    assert config.user_agent is None
    assert config.profile_dir is None
    assert config.user_data_dir == (
        tmp_path
        / "xdg"
        / "paper-fetch"
        / "publisher-browser-profiles"
        / "annualreviews-camoufox"
    )


def test_camoufox_generic_profile_override(tmp_path) -> None:
    profile = tmp_path / "profile"
    config = CamoufoxBackend().load_runtime_config(
        {
            BROWSER_PROFILE_DIR_ENV_VAR: str(profile),
            XDG_DATA_HOME_ENV_VAR: str(tmp_path / "xdg"),
        },
        provider="acs",
        doi="10.1021/example",
    )
    assert config.profile_dir == profile
    assert config.user_data_dir is None


def test_camoufox_context_options_do_not_override_fingerprint(tmp_path) -> None:
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1000/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent="must-not-be-used",
        backend="camoufox",
    )

    options = context_options_for_config(config)

    assert options == {"accept_downloads": True}
    assert "user_agent" not in options
    assert "viewport" not in options
    assert "locale" not in options


def test_camoufox_manager_reuses_browser_and_creates_fresh_contexts(
    monkeypatch,
) -> None:
    browser = object()
    contexts = [object(), object()]
    playwright = SimpleNamespace(stop=mock.Mock())
    playwright_manager = SimpleNamespace(start=mock.Mock(return_value=playwright))
    sync_playwright = mock.Mock(return_value=playwright_manager)
    new_browser = mock.Mock(return_value=browser)
    new_context = mock.Mock(side_effect=contexts)

    def import_module(name: str):
        if name == "playwright.sync_api":
            return SimpleNamespace(sync_playwright=sync_playwright)
        if name == "camoufox.sync_api":
            return SimpleNamespace(NewBrowser=new_browser, NewContext=new_context)
        raise AssertionError(name)

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        import_module,
    )
    manager = CamoufoxBrowserManager(binary_path="/runtime/camoufox", headless=True)

    assert manager.new_context(accept_downloads=True) is contexts[0]
    assert manager.new_context(accept_downloads=True) is contexts[1]
    assert new_browser.call_count == 1
    assert new_context.call_count == 2
    new_browser.assert_called_once_with(
        playwright,
        persistent_context=False,
        headless=True,
        executable_path="/runtime/camoufox",
    )


def test_camoufox_manager_stops_playwright_when_runtime_fetch_fails(
    monkeypatch,
) -> None:
    playwright = SimpleNamespace(stop=mock.Mock())
    playwright_manager = SimpleNamespace(start=mock.Mock(return_value=playwright))

    def import_module(name: str):
        if name == "playwright.sync_api":
            return SimpleNamespace(
                sync_playwright=mock.Mock(return_value=playwright_manager)
            )
        if name == "camoufox.sync_api":
            return SimpleNamespace(NewBrowser=mock.Mock())
        raise AssertionError(name)

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager._launch_executable_path",
        mock.Mock(side_effect=RuntimeError("download failed")),
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        import_module,
    )

    with pytest.raises(RuntimeError, match="download failed"):
        CamoufoxBrowserManager().browser()

    playwright.stop.assert_called_once_with()


def test_camoufox_first_launch_uses_official_runtime_fetcher(monkeypatch) -> None:
    runtime_path = object()
    pkgman = SimpleNamespace(
        camoufox_path=mock.Mock(return_value=runtime_path),
        launch_path=mock.Mock(return_value="/runtime/camoufox"),
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        lambda name: (
            pkgman
            if name == "camoufox.pkgman"
            else pytest.fail(f"unexpected module import: {name}")
        ),
    )

    assert _launch_executable_path(None) == "/runtime/camoufox"
    pkgman.camoufox_path.assert_called_once_with(download_if_missing=True)
    pkgman.launch_path.assert_called_once_with(runtime_path)


def test_camoufox_static_probe_reads_runtime_without_fetching(
    monkeypatch, tmp_path
) -> None:
    active_version = "browsers/official/test-version"
    runtime_path = tmp_path / active_version
    runtime_path.mkdir(parents=True)
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"active_version": "browsers/official/test-version"}',
        encoding="utf-8",
    )
    forbidden_fetch = mock.Mock(side_effect=AssertionError("must not fetch"))
    pkgman = SimpleNamespace(
        INSTALL_DIR=tmp_path,
        camoufox_path=forbidden_fetch,
    )
    multiversion = SimpleNamespace(CONFIG_FILE=config_path)

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox.importlib_util.find_spec",
        lambda _name: object(),
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox.importlib_metadata.version",
        lambda _name: "test-version",
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox.importlib.import_module",
        lambda name: (
            pkgman
            if name == "camoufox.pkgman"
            else multiversion
            if name == "camoufox.multiversion"
            else pytest.fail(f"unexpected module import: {name}")
        ),
    )

    details = _dependency_details()

    assert details["runtime_installed"] is True
    assert details["runtime_path"] == str(runtime_path)
    forbidden_fetch.assert_not_called()


def test_runtime_context_closes_camoufox_on_owning_worker_thread() -> None:
    runtime = RuntimeContext(env={})
    manager = SimpleNamespace(close=mock.Mock())
    key = (threading.get_ident(), True, "/runtime/camoufox")
    runtime._camoufox_browser_managers[key] = manager

    runtime.close_camoufox_for_current_thread()

    manager.close.assert_called_once_with()
    assert key not in runtime._camoufox_browser_managers


class _Response:
    status = 200
    headers = {"content-type": "text/html"}

    def all_headers(self):
        return dict(self.headers)


class _Page:
    def __init__(self) -> None:
        self.url = "https://example.test/article"
        self.goto_kwargs: dict[str, object] = {}
        self.route_handler = None

    def goto(self, url: str, **kwargs):
        self.url = url
        self.goto_kwargs = dict(kwargs)
        return _Response()

    def route(self, _pattern: str, handler) -> None:
        self.route_handler = handler

    def content(self) -> str:
        return "<html><head><title>Article</title></head><body><main>Full text</main></body></html>"

    def title(self) -> str:
        return "Article"

    def evaluate(self, _script: str):
        return "Mozilla/5.0 Firefox/152.0"

    def close(self) -> None:
        pass


class _Context:
    def __init__(self) -> None:
        self.page = _Page()

    def new_page(self):
        return self.page

    def cookies(self, _urls=None):
        return []

    def close(self) -> None:
        pass


def test_camoufox_html_navigation_uses_commit_and_keeps_images(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="annualreviews",
        doi="10.1146/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
        backend="camoufox",
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        lambda *_args, **_kwargs: SimpleNamespace(attempted=True, ready=True),
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://example.test/article"],
        publisher="annualreviews",
        config=config,
        wait_seconds=0,
        disable_media=True,
    )

    assert result.response_status == 200
    assert result.diagnostics["browser_runtime_trace"]["backend"] == "camoufox"
    assert context.page.goto_kwargs["wait_until"] == "commit"

    image_route = mock.Mock()
    image_route.request.resource_type = "image"
    context.page.route_handler(image_route)
    image_route.continue_.assert_called_once()
    image_route.abort.assert_not_called()
