from __future__ import annotations

import json
from types import SimpleNamespace
import subprocess
import threading
from unittest import mock

import pytest

from paper_fetch.config import (
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
    CamoufoxPersistentContextManager,
    _launch_executable_path,
    _launch_firefox_major_version,
)
from paper_fetch.providers.browser_runtime import preparation
from paper_fetch.providers.browser_runtime.preparation import CamoufoxRuntimeProbe
from paper_fetch.providers.browser_runtime.context import context_options_for_config
from paper_fetch.providers.browser_runtime import context as browser_runtime_context
from paper_fetch.providers.browser_runtime.types import (
    BrowserHtmlReadiness,
    BrowserRuntimeConfig,
)
from paper_fetch.runtime import RuntimeContext


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
    )

    with pytest.raises(RuntimeError, match="camoufox failed"):
        browser_runtime_context.open_browser_context(config)

    camoufox_manager.assert_called_once()


def test_camoufox_config_uses_generic_settings_and_separate_profile(tmp_path) -> None:
    executable = tmp_path / "camoufox"
    executable.write_text("runtime", encoding="utf-8")
    executable.chmod(0o755)
    env = {
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
    )

    options = context_options_for_config(config)

    assert options == {"accept_downloads": True}
    assert "user_agent" not in options
    assert "viewport" not in options
    assert "locale" not in options


def test_open_context_records_successful_storage_state_injection(tmp_path) -> None:
    state = tmp_path / "storage-state.json"
    state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1002/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        storage_state_path=state,
    )
    browser_context = object()
    runtime = SimpleNamespace(
        new_browser_context_for_runtime_config=mock.Mock(return_value=browser_context),
        record_browser_state_capability_use=mock.Mock(),
    )

    manager, opened = browser_runtime_context.open_browser_context(
        config, runtime_context=runtime
    )

    assert manager is None
    assert opened is browser_context
    runtime.new_browser_context_for_runtime_config.assert_called_once_with(
        config,
        accept_downloads=True,
        storage_state=str(state),
    )
    runtime.record_browser_state_capability_use.assert_called_once_with(
        provider="wiley",
        backend="camoufox",
        storage_state_path=state,
    )


def test_open_context_failure_does_not_record_storage_state_use(tmp_path) -> None:
    state = tmp_path / "storage-state.json"
    state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1002/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        storage_state_path=state,
    )
    runtime = SimpleNamespace(
        new_browser_context_for_runtime_config=mock.Mock(
            side_effect=RuntimeError("context failed")
        ),
        record_browser_state_capability_use=mock.Mock(),
    )

    with pytest.raises(RuntimeError, match="context failed"):
        browser_runtime_context.open_browser_context(config, runtime_context=runtime)

    runtime.record_browser_state_capability_use.assert_not_called()


def test_open_wiley_context_without_storage_state_has_no_state_capability_use(
    tmp_path,
) -> None:
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1111/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        profile_dir=None,
        user_data_dir=None,
        storage_state_path=None,
        persist_storage_state=False,
    )
    browser_context = object()
    runtime = SimpleNamespace(
        new_browser_context_for_runtime_config=mock.Mock(return_value=browser_context),
        record_browser_state_capability_use=mock.Mock(),
    )

    manager, opened = browser_runtime_context.open_browser_context(
        config, runtime_context=runtime
    )

    assert manager is None
    assert opened is browser_context
    runtime.new_browser_context_for_runtime_config.assert_called_once_with(
        config,
        accept_downloads=True,
    )
    runtime.record_browser_state_capability_use.assert_not_called()
    assert not list(tmp_path.rglob("storage-state.json"))


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
        "paper_fetch.providers.browser_runtime.camoufox_manager._launch_firefox_major_version",
        lambda _path: 152,
    )
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
        ff_version=152,
        i_know_what_im_doing=True,
    )
    assert new_context.call_args_list == [
        mock.call(browser, accept_downloads=True, ff_version="152"),
        mock.call(browser, accept_downloads=True, ff_version="152"),
    ]


def test_camoufox_startup_output_is_kept_off_protocol_stdout(
    monkeypatch, capsys
) -> None:
    browser = SimpleNamespace(close=mock.Mock())
    playwright = SimpleNamespace(stop=mock.Mock())
    playwright_manager = SimpleNamespace(start=mock.Mock(return_value=playwright))

    def new_browser(*_args, **_kwargs):
        print("Extracting addon (UBO): Complete")
        return browser

    def import_module(name: str):
        if name == "playwright.sync_api":
            return SimpleNamespace(
                sync_playwright=mock.Mock(return_value=playwright_manager)
            )
        if name == "camoufox.sync_api":
            return SimpleNamespace(NewBrowser=new_browser)
        raise AssertionError(name)

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager._launch_firefox_major_version",
        lambda _path: None,
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        import_module,
    )
    manager = CamoufoxBrowserManager(
        binary_path="/runtime/camoufox",
        headless=True,
    )

    assert manager.browser() is browser
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Extracting addon (UBO): Complete" in captured.err
    manager.close()


def test_camoufox_official_runtime_path_is_resolved_by_package(monkeypatch) -> None:
    runtime_path = object()
    pkgman = SimpleNamespace(
        camoufox_path=mock.Mock(return_value=runtime_path),
        launch_path=mock.Mock(
            return_value="/runtime/Camoufox.app/Contents/MacOS/camoufox"
        ),
    )
    browser = SimpleNamespace(close=mock.Mock())
    playwright = SimpleNamespace(stop=mock.Mock())
    playwright_manager = SimpleNamespace(start=mock.Mock(return_value=playwright))
    new_browser = mock.Mock(return_value=browser)

    def import_module(name: str):
        if name == "camoufox.pkgman":
            return pkgman
        if name == "playwright.sync_api":
            return SimpleNamespace(
                sync_playwright=mock.Mock(return_value=playwright_manager)
            )
        if name == "camoufox.sync_api":
            return SimpleNamespace(NewBrowser=new_browser)
        raise AssertionError(name)

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        import_module,
    )

    manager = CamoufoxBrowserManager(headless=True)
    assert manager.browser() is browser
    manager.close()

    pkgman.camoufox_path.assert_called_once_with(download_if_missing=False)
    pkgman.launch_path.assert_not_called()
    new_browser.assert_called_once_with(
        playwright,
        persistent_context=False,
        headless=True,
    )


def test_camoufox_manager_only_resolves_prepared_runtime_without_downloading(
    monkeypatch,
) -> None:
    order: list[str] = []
    browser = SimpleNamespace(close=mock.Mock())
    playwright = SimpleNamespace(stop=mock.Mock())
    playwright_manager = SimpleNamespace(start=mock.Mock(return_value=playwright))
    pkgman = SimpleNamespace(
        camoufox_path=mock.Mock(side_effect=lambda **_kwargs: order.append("resolve"))
    )

    def import_module(name: str):
        if name == "camoufox.pkgman":
            return pkgman
        if name == "playwright.sync_api":
            return SimpleNamespace(
                sync_playwright=mock.Mock(return_value=playwright_manager)
            )
        if name == "camoufox.sync_api":
            return SimpleNamespace(NewBrowser=mock.Mock(return_value=browser))
        raise AssertionError(name)

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        import_module,
    )

    manager = CamoufoxBrowserManager(headless=True)
    assert manager.browser() is browser
    manager.close()

    assert order == ["resolve"]
    pkgman.camoufox_path.assert_called_once_with(download_if_missing=False)


def test_camoufox_persistent_official_runtime_path_is_resolved_by_package(
    monkeypatch, tmp_path
) -> None:
    runtime_path = object()
    pkgman = SimpleNamespace(
        camoufox_path=mock.Mock(return_value=runtime_path),
        launch_path=mock.Mock(
            return_value="/runtime/Camoufox.app/Contents/MacOS/camoufox"
        ),
    )
    context = SimpleNamespace(close=mock.Mock())
    playwright = SimpleNamespace(stop=mock.Mock())
    playwright_manager = SimpleNamespace(start=mock.Mock(return_value=playwright))
    new_browser = mock.Mock(return_value=context)

    def import_module(name: str):
        if name == "camoufox.pkgman":
            return pkgman
        if name == "playwright.sync_api":
            return SimpleNamespace(
                sync_playwright=mock.Mock(return_value=playwright_manager)
            )
        if name == "camoufox.sync_api":
            return SimpleNamespace(NewBrowser=new_browser)
        raise AssertionError(name)

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        import_module,
    )

    manager = CamoufoxPersistentContextManager(
        user_data_dir=str(tmp_path / "profile"),
        headless=False,
    )
    assert manager.new_context() is context
    manager.close()

    pkgman.camoufox_path.assert_called_once_with(download_if_missing=False)
    pkgman.launch_path.assert_not_called()
    new_browser.assert_called_once_with(
        playwright,
        persistent_context=True,
        headless=False,
        user_data_dir=str(tmp_path / "profile"),
    )


def test_camoufox_persistent_explicit_binary_path_is_forwarded(
    monkeypatch, tmp_path
) -> None:
    version_type = SimpleNamespace(
        from_path=mock.Mock(side_effect=OSError("no adjacent metadata"))
    )
    pkgman = SimpleNamespace(Version=version_type)
    context = SimpleNamespace(close=mock.Mock())
    playwright = SimpleNamespace(stop=mock.Mock())
    playwright_manager = SimpleNamespace(start=mock.Mock(return_value=playwright))
    new_browser = mock.Mock(return_value=context)

    def import_module(name: str):
        if name == "camoufox.pkgman":
            return pkgman
        if name == "playwright.sync_api":
            return SimpleNamespace(
                sync_playwright=mock.Mock(return_value=playwright_manager)
            )
        if name == "camoufox.sync_api":
            return SimpleNamespace(NewBrowser=new_browser)
        raise AssertionError(name)

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        import_module,
    )

    manager = CamoufoxPersistentContextManager(
        user_data_dir=str(tmp_path / "profile"),
        binary_path="/custom/camoufox",
        headless=False,
    )
    assert manager.new_context() is context
    manager.close()

    new_browser.assert_called_once_with(
        playwright,
        persistent_context=True,
        headless=False,
        user_data_dir=str(tmp_path / "profile"),
        executable_path="/custom/camoufox",
    )
    assert version_type.from_path.call_count == 2


def test_camoufox_manager_stops_playwright_when_runtime_readiness_check_fails(
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
        mock.Mock(side_effect=RuntimeError("runtime not prepared")),
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        import_module,
    )

    with pytest.raises(RuntimeError, match="runtime not prepared"):
        CamoufoxBrowserManager().browser()

    playwright.stop.assert_called_once_with()


def test_camoufox_first_launch_requires_prepared_official_runtime(monkeypatch) -> None:
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

    assert _launch_executable_path(None) is None
    pkgman.camoufox_path.assert_called_once_with(download_if_missing=False)
    pkgman.launch_path.assert_not_called()


def test_explicit_camoufox_executable_reuses_adjacent_version_metadata(
    tmp_path, monkeypatch
) -> None:
    runtime_dir = tmp_path / "camoufox-runtime"
    runtime_dir.mkdir()
    executable = runtime_dir / "camoufox-bin"
    executable.touch()
    version = SimpleNamespace(version="152.0.4")
    version_type = SimpleNamespace(from_path=mock.Mock(return_value=version))
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.importlib.import_module",
        lambda name: (
            SimpleNamespace(Version=version_type)
            if name == "camoufox.pkgman"
            else pytest.fail(f"unexpected module import: {name}")
        ),
    )

    assert _launch_firefox_major_version(str(executable)) == 152
    version_type.from_path.assert_called_once_with(runtime_dir)


def test_camoufox_static_probe_reads_runtime_without_fetching(
    monkeypatch, tmp_path
) -> None:
    active_version = "browsers/official/test-version"
    runtime_path = tmp_path / active_version
    runtime_path.mkdir(parents=True)
    executable = runtime_path / "camoufox"
    executable.touch()

    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox.importlib_util.find_spec",
        lambda _name: object(),
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox.importlib_metadata.version",
        lambda _name: "test-version",
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox.probe_camoufox_managed_runtime",
        lambda: CamoufoxRuntimeProbe(
            state="ready",
            installed=True,
            valid=True,
            runtime_path=runtime_path,
            executable_path=executable,
            version="test-version",
            active_spec=active_version,
            managed_path_safe=True,
        ),
    )

    details = _dependency_details()

    assert details["runtime_installed"] is True
    assert details["package_ready"] is True
    assert details["download_required"] is False
    assert details["runtime_path"] == str(runtime_path)


def test_camoufox_probe_validates_managed_executable_without_fetching(
    monkeypatch, tmp_path
) -> None:
    active_spec = "browsers/official/152.0.4-beta.28"
    runtime_path = tmp_path / active_spec
    executable = runtime_path / "camoufox"
    executable.parent.mkdir(parents=True)
    executable.touch()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"active_version": active_spec}),
        encoding="utf-8",
    )
    version = SimpleNamespace(
        full_string="152.0.4-beta.28",
        is_supported=lambda: True,
    )
    version_type = SimpleNamespace(from_path=mock.Mock(return_value=version))
    pkgman = SimpleNamespace(
        INSTALL_DIR=tmp_path,
        Version=version_type,
        launch_path=mock.Mock(return_value=str(executable)),
    )
    multiversion = SimpleNamespace(CONFIG_FILE=config_path)
    monkeypatch.setattr(
        preparation,
        "import_module",
        lambda name: pkgman if name == "camoufox.pkgman" else multiversion,
    )

    probe = preparation.probe_camoufox_managed_runtime()

    assert probe.valid is True
    assert probe.runtime_path == runtime_path
    assert probe.executable_path == executable
    version_type.from_path.assert_called_once_with(runtime_path)
    pkgman.launch_path.assert_called_once_with(runtime_path)


def test_camoufox_probe_rejects_link_in_managed_runtime_path(
    monkeypatch, tmp_path
) -> None:
    real_parent = tmp_path / "real-official"
    real_parent.mkdir()
    browsers = tmp_path / "browsers"
    browsers.mkdir()
    try:
        (browsers / "official").symlink_to(real_parent, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")
    (real_parent / "152.0.4-beta.28").mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"active_version":"browsers/official/152.0.4-beta.28"}',
        encoding="utf-8",
    )
    pkgman = SimpleNamespace(INSTALL_DIR=tmp_path)
    multiversion = SimpleNamespace(CONFIG_FILE=config_path)
    monkeypatch.setattr(
        preparation,
        "import_module",
        lambda name: pkgman if name == "camoufox.pkgman" else multiversion,
    )

    probe = preparation.probe_camoufox_managed_runtime()

    assert probe.valid is False
    assert probe.managed_path_safe is False
    assert probe.state == "corrupt"


def test_camoufox_probe_rejects_reparse_attribute_without_isjunction(
    monkeypatch,
) -> None:
    path = mock.Mock()
    path.is_symlink.return_value = False
    path.lstat.return_value = SimpleNamespace(st_file_attributes=0x400)
    monkeypatch.setattr(preparation.os.path, "isjunction", None, raising=False)

    assert preparation._is_link_or_reparse(path) is True


def test_camoufox_probe_rejects_parent_traversal(tmp_path) -> None:
    candidate, safe = preparation._managed_candidate(
        tmp_path,
        "browsers/../unexpected-runtime",
    )

    assert candidate == tmp_path / "browsers" / ".." / "unexpected-runtime"
    assert safe is False


def test_camoufox_runtime_readiness_rejects_missing_runtime_without_download(
    monkeypatch, tmp_path
) -> None:
    backend = CamoufoxBackend()
    config = BrowserRuntimeConfig(
        provider="science",
        doi="10.1126/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox._dependency_details",
        lambda: {
            "packages": {"playwright": True, "camoufox": True},
            "package_ready": True,
            "runtime_installed": False,
            "download_required": True,
        },
    )
    monkeypatch.setattr(
        subprocess,
        "Popen",
        mock.Mock(side_effect=AssertionError("readiness must not spawn a process")),
    )

    with pytest.raises(ProviderFailure, match="runtime is missing"):
        backend.ensure_runtime_ready(config)


def test_camoufox_status_distinguishes_package_and_runtime_readiness(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox._dependency_details",
        lambda: {
            "packages": {"playwright": True, "camoufox": True},
            "package_ready": True,
            "runtime_installed": False,
            "download_required": True,
            "runtime_path": None,
        },
    )

    result = CamoufoxBackend().probe_runtime_status({}, provider="science")
    checks = {check.name: check for check in result.checks}

    assert result.status == "not_configured"
    assert checks["playwright_dependency"].status == "ok"
    assert checks["browser_runtime"].status == "not_configured"
    assert checks["browser_runtime"].details["download_required"] is True


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
        self.wait_for_function = mock.Mock()
        self.wait_for_selector = mock.Mock()
        self.wait_for_timeout = mock.Mock()

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
        self.added_cookies: list[dict[str, object]] = []
        self.events: list[str] = []
        self.route_handler = None

    def add_cookies(self, cookies):
        self.events.append("add_cookies")
        self.added_cookies.extend(cookies)

    def route(self, _pattern: str, handler) -> None:
        self.route_handler = handler

    def new_page(self):
        self.events.append("new_page")
        return self.page

    def cookies(self, _urls=None):
        return []

    def close(self) -> None:
        pass


def _wiley_review_html(
    identity_markup: str,
    *,
    body_prefix: str = "",
    body_suffix: str = "",
) -> str:
    return (
        "<html><head><title>Open access article</title>"
        f"{identity_markup}</head><body>"
        "<nav>Login / Register Individual login Institutional login Open Access</nav>"
        "<section class='article-section__content en main'>"
        "<h2>Results</h2>"
        f"{body_prefix}<p>"
        + ("Substantive Wiley article body text. " * 120)
        + "</p><p>Additional discussion paragraph.</p>"
        f"{body_suffix}</section></body></html>"
    )


def _stable_wiley_readiness() -> SimpleNamespace:
    return SimpleNamespace(
        attempted=True,
        ready=True,
        selector="section.article-section__content",
        text_length=4200,
        paragraph_count=2,
        heading_count=1,
        fingerprint="stable-wiley-body",
    )


def test_browser_candidate_uses_native_navigation_without_context_guard(
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
    )
    open_context = mock.Mock(return_value=(None, context))
    monkeypatch.setattr(_playwright_browser, "open_browser_context", open_context)

    result = _playwright_browser.fetch_html_with_playwright(
        ["http://127.0.0.1:8080/internal"],
        publisher="annualreviews",
        config=config,
        wait_seconds=0,
    )

    assert result.final_url == "http://127.0.0.1:8080/internal"
    open_context.assert_called_once()
    assert context.route_handler is None


def test_camoufox_html_retry_applies_provider_seed_before_page_creation(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="aip",
        doi="10.1063/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
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
        ["https://pubs.aip.org/aip/adv/article/1/1/example"],
        publisher="aip",
        config=config,
        wait_seconds=0,
        browser_context_seed={
            "browser_cookies": [
                {
                    "name": "__cf_bm",
                    "value": "private-value",
                    "domain": ".aip.org",
                    "path": "/",
                },
                {
                    "name": "unrelated",
                    "value": "drop-me",
                    "domain": ".example.test",
                    "path": "/",
                },
            ],
            "browser_user_agent": "must-not-override-camoufox",
        },
    )

    assert context.events[:2] == ["add_cookies", "new_page"]
    assert [cookie["name"] for cookie in context.added_cookies] == ["__cf_bm"]
    seed_trace = result.diagnostics["browser_runtime_trace"]["browser_context_seed"]
    assert seed_trace == {
        "provided": True,
        "cookie_count": 1,
        "applied": True,
        "user_agent_reused": False,
        "reason": "cookies_applied",
    }
    assert "private-value" not in str(result.diagnostics)
    assert "must-not-override-camoufox" not in str(result.diagnostics)


def test_camoufox_html_retry_rejects_invalid_seed_without_logging_cookie_value(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    context.add_cookies = mock.Mock(
        side_effect=RuntimeError("invalid cookie private-cookie-value")
    )
    config = BrowserRuntimeConfig(
        provider="aip",
        doi="10.1063/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )

    with pytest.raises(browser_runtime.BrowserRuntimeFailure) as captured:
        _playwright_browser.fetch_html_with_playwright(
            ["https://pubs.aip.org/aip/adv/article/1/1/example"],
            publisher="aip",
            config=config,
            browser_context_seed={
                "browser_cookies": [
                    {
                        "name": "__cf_bm",
                        "value": "private-cookie-value",
                        "domain": ".aip.org",
                        "path": "/",
                    }
                ]
            },
        )

    assert captured.value.kind == "invalid_browser_context_seed"
    assert "private-cookie-value" not in captured.value.message
    assert "private-cookie-value" not in str(captured.value.details)
    assert captured.value.details["trace"]["browser_context_seed"] == {
        "provided": True,
        "cookie_count": 1,
        "applied": False,
        "user_agent_reused": False,
        "reason": "cookie_injection_failed",
        "error_type": "RuntimeError",
    }


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
    image_route.request.url = context.page.url
    context.page.route_handler(image_route)
    image_route.continue_.assert_called_once()
    image_route.abort.assert_not_called()


def test_main_document_diagnostics_distinguish_finished_response_from_loading_shell(
    monkeypatch, tmp_path
) -> None:
    class Request:
        resource_type = "document"
        failure = None

        def __init__(self, url: str) -> None:
            self.url = url

    class Response:
        status = 200

        def __init__(self, request: Request, headers: dict[str, str]) -> None:
            self.request = request
            self.url = request.url
            self.headers = headers

        def all_headers(self):
            return dict(self.headers)

    class LifecyclePage(_Page):
        def __init__(
            self,
            *,
            html: str,
            finished: bool,
            headers: dict[str, str],
            navigation_timing: dict[str, object],
        ) -> None:
            super().__init__()
            self._html = html
            self._finished = finished
            self._headers = headers
            self._navigation_timing = navigation_timing
            self._listeners: dict[str, list[object]] = {}

        def on(self, event: str, callback) -> None:
            self._listeners.setdefault(event, []).append(callback)

        def remove_listener(self, event: str, callback) -> None:
            self._listeners.get(event, []).remove(callback)

        def _emit(self, event: str, value: object) -> None:
            for callback in self._listeners.get(event, []):
                callback(value)

        def goto(self, url: str, **kwargs):
            self.url = url
            self.goto_kwargs = dict(kwargs)
            request = Request(url)
            response = Response(request, self._headers)
            self._emit("request", request)
            self._emit("response", response)
            if self._finished:
                self._emit("requestfinished", request)
            return response

        def content(self) -> str:
            return self._html

        def evaluate(self, script: str, *_args):
            if (
                script
                == _playwright_browser._MAIN_DOCUMENT_NAVIGATION_DIAGNOSTIC_SCRIPT
            ):
                return self._navigation_timing
            return "Mozilla/5.0 Firefox/152.0"

    def fetch_with_page(page: LifecyclePage, name: str):
        context = _Context()
        context.page = page
        config = BrowserRuntimeConfig(
            provider="aip",
            doi="10.1063/example",
            artifact_dir=tmp_path / name,
            headless=True,
            user_agent=None,
            persist_storage_state=False,
        )
        monkeypatch.setattr(
            _playwright_browser,
            "open_browser_context",
            lambda *_args, **_kwargs: (None, context),
        )
        return _playwright_browser.fetch_html_with_playwright(
            ["https://pubs.aip.org/doi/full/10.1063/example"],
            publisher="aip",
            config=config,
            wait_seconds=0,
        )

    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        lambda *_args, **_kwargs: SimpleNamespace(
            attempted=True,
            ready=False,
            selector=None,
            text_length=0,
            paragraph_count=0,
            heading_count=0,
        ),
    )
    complete_html = "<html><head><title>Article</title></head><body>Body</body></html>"
    complete = fetch_with_page(
        LifecyclePage(
            html=complete_html,
            finished=True,
            headers={
                "content-type": "text/html; charset=utf-8",
                "content-length": "2048",
            },
            navigation_timing={
                "documentReadyState": "complete",
                "navigation": {
                    "type": "navigate",
                    "nextHopProtocol": "h2",
                    "responseStart": 12.5,
                    "responseEnd": 30.5,
                    "domInteractive": 32.0,
                    "domContentLoadedEventEnd": 35.0,
                    "loadEventEnd": 40.0,
                    "duration": 40.0,
                    "transferSize": 2300,
                    "encodedBodySize": 2048,
                    "decodedBodySize": 4096,
                },
            },
        ),
        "complete",
    )
    loading_html = "<html><head><title>Article</title></head></html>"
    loading = fetch_with_page(
        LifecyclePage(
            html=loading_html,
            finished=False,
            headers={
                "content-type": "text/html",
                "transfer-encoding": "chunked",
                "set-cookie": "session=private-value",
            },
            navigation_timing={
                "documentReadyState": "loading",
                "navigation": {
                    "type": "navigate",
                    "nextHopProtocol": "h2",
                    "responseStart": 10.0,
                    "responseEnd": 0.0,
                    "domInteractive": 0.0,
                    "domContentLoadedEventEnd": 0.0,
                    "loadEventEnd": 0.0,
                    "duration": 0.0,
                    "transferSize": 1056,
                    "encodedBodySize": 1056,
                    "decodedBodySize": 1056,
                },
            },
        ),
        "loading",
    )

    complete_trace = complete.diagnostics["browser_runtime_trace"]
    complete_document = complete_trace["candidates"][0]["main_document_response"]
    assert complete_document["content_length_bytes"] == 2048
    assert complete_document["captured_html_bytes"] == len(
        complete_html.encode("utf-8")
    )
    assert complete_document["request_lifecycle"]["request_finished_observed"] is True
    assert complete_document["navigation_timing"] == {
        "available": True,
        "document_ready_state": "complete",
        "navigation_entry_present": True,
        "response_start_ms": 12.5,
        "response_end_ms": 30.5,
        "dom_interactive_ms": 32,
        "dom_content_loaded_event_end_ms": 35,
        "load_event_end_ms": 40,
        "duration_ms": 40,
        "transfer_size_bytes": 2300,
        "encoded_body_size_bytes": 2048,
        "decoded_body_size_bytes": 4096,
        "navigation_type": "navigate",
        "next_hop_protocol": "h2",
        "response_completed": True,
        "dom_content_loaded_completed": True,
        "load_event_completed": True,
    }
    assert (
        complete_trace["page_events"]["document_requests"][0][
            "request_finished_observed"
        ]
        is True
    )

    loading_trace = loading.diagnostics["browser_runtime_trace"]
    loading_document = loading_trace["candidates"][0]["main_document_response"]
    assert loading_document["content_length_bytes"] is None
    assert loading_document["transfer_encoding_present"] is True
    assert loading_document["chunked_transfer_declared"] is True
    assert loading_document["captured_html_bytes"] == len(loading_html.encode("utf-8"))
    assert loading_document["request_lifecycle"]["request_finished_observed"] is False
    assert loading_document["navigation_timing"]["document_ready_state"] == "loading"
    assert loading_document["navigation_timing"]["response_end_ms"] == 0
    assert loading_document["navigation_timing"]["encoded_body_size_bytes"] == 1056
    assert loading_document["navigation_timing"]["response_completed"] is False
    assert "private-value" not in str(loading_trace)


def test_camoufox_trace_reports_storage_state_was_loaded(monkeypatch, tmp_path) -> None:
    context = _Context()
    state = tmp_path / "storage-state.json"
    state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    config = BrowserRuntimeConfig(
        provider="annualreviews",
        doi="10.1146/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
        storage_state_path=state,
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
    )

    assert result.diagnostics["browser_runtime_trace"]["storage_state_load"] == {
        "path": str(state),
        "exists": True,
        "used": True,
    }


def test_wiley_body_readiness_defers_login_navigation_paywall_text(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    context.page.content = mock.Mock(
        return_value=(
            "<html><head><title>Open access article</title></head><body>"
            "<nav>Login / Register Individual login Institutional login Open Access</nav>"
            "<section class='article-section__content en main'>"
            "<h2>Results</h2><p>"
            + ("Substantive Wiley article body text. " * 120)
            + "</p><p>Additional discussion paragraph.</p></section></body></html>"
        )
    )
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1111/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        lambda *_args, **_kwargs: _stable_wiley_readiness(),
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://onlinelibrary.wiley.com/doi/full/10.1111/example"],
        publisher="wiley",
        config=config,
        wait_seconds=2,
    )

    assert result.response_status == 200
    assert "Institutional login" in result.summary
    candidate = result.diagnostics["browser_runtime_trace"]["candidates"][0]
    assert candidate["dom_readiness_ready"] is True
    assert candidate["result"] == "success"


@pytest.mark.parametrize(
    ("identity_markup", "expected_source"),
    [
        pytest.param(
            "<meta name='citation_doi' content='10.1111/example'>",
            "citation_meta",
            id="citation-meta",
        ),
        pytest.param(
            "<link rel='canonical' href='https://onlinelibrary.wiley.com/doi/10.1111/example'>",
            "canonical",
            id="canonical",
        ),
        pytest.param(
            "<span class='epub-doi'>https://doi.org/10.1111/example</span>",
            "epub_doi",
            id="epub-doi",
        ),
    ],
)
def test_wiley_403_confirmed_body_and_identity_preserves_status(
    monkeypatch,
    tmp_path,
    identity_markup,
    expected_source,
) -> None:
    context = _Context()
    context.page.content = mock.Mock(return_value=_wiley_review_html(identity_markup))

    def goto(url: str, **_kwargs):
        context.page.url = url
        response = _Response()
        response.status = 403
        return response

    context.page.goto = goto
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1111/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        profile_dir=None,
        user_data_dir=None,
        storage_state_path=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        lambda *_args, **_kwargs: _stable_wiley_readiness(),
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://onlinelibrary.wiley.com/doi/10.1111/example"],
        publisher="wiley",
        config=config,
        wait_seconds=2,
    )

    assert result.response_status == 403
    assert "Substantive Wiley article body text" in result.html
    trace = result.diagnostics["browser_runtime_trace"]
    candidate = trace["candidates"][0]
    review = candidate["http_access_status_review"]
    assert candidate["result"] == "success"
    assert candidate["status"] == 403
    assert candidate["dom_readiness_ready"] is True
    assert candidate["dom_readiness_fingerprint_present"] is True
    assert review == {
        "status": 403,
        "body_ready": True,
        "doi_evidence_present": True,
        "doi_evidence_sources": [expected_source],
        "doi_match": True,
        "doi_match_sources": [expected_source],
        "blocking_signals": [],
        "candidate_confirmed": True,
        "status_override_applied": True,
        "fulltext_acceptance": "pending",
        "accepted": False,
        "reason": "pending_fulltext_acceptance",
    }
    assert trace["storage_state_load"] == {
        "path": None,
        "exists": False,
        "used": False,
    }
    assert trace["storage_state_save"]["reason"] == "storage_state_write_disabled"
    assert not list(tmp_path.rglob("storage-state.json"))


@pytest.mark.parametrize(
    ("html", "body_ready", "expected_reason", "expected_signal"),
    [
        pytest.param(
            "<html><head><title>Article</title></head></html>",
            False,
            "body_not_ready",
            None,
            id="empty-shell",
        ),
        pytest.param(
            _wiley_review_html("<meta name='citation_doi' content='10.1111/example'>"),
            False,
            "body_not_ready",
            None,
            id="unstable-body",
        ),
        pytest.param(
            _wiley_review_html(""),
            True,
            "doi_evidence_missing",
            None,
            id="missing-doi",
        ),
        pytest.param(
            _wiley_review_html(
                "<meta name='citation_doi' content='10.1111/different'>"
            ),
            True,
            "doi_mismatch",
            None,
            id="mismatched-doi",
        ),
        pytest.param(
            _wiley_review_html(
                "<meta name='citation_doi' content='10.1111/example'>",
                body_prefix="<p>Checking your browser before accessing the site.</p>",
            ),
            True,
            "blocking_signal",
            "cloudflare_challenge",
            id="challenge",
        ),
        pytest.param(
            _wiley_review_html(
                "<meta name='citation_doi' content='10.1111/example'>",
                body_prefix="<div data-article-access='no'>No access</div>",
            ),
            True,
            "blocking_signal",
            "data_article_access_no",
            id="explicit-no-access",
        ),
        pytest.param(
            _wiley_review_html(
                "<meta name='citation_doi' content='10.1111/example'>",
                body_suffix=(
                    "<script>window.adobeDataLayer.push({"
                    '"content":{"item":{"access":"no"}}'
                    "});</script>"
                ),
            ),
            True,
            "blocking_signal",
            "wiley_access_no",
            id="datalayer-no-access",
        ),
        pytest.param(
            _wiley_review_html(
                "<meta name='citation_doi' content='10.1111/example'>",
                body_prefix="<p>Purchase access to continue reading this article.</p>",
            ),
            True,
            "blocking_signal",
            "purchase access",
            id="paywall",
        ),
    ],
)
def test_wiley_403_review_rejects_unconfirmed_candidate(
    monkeypatch,
    tmp_path,
    html,
    body_ready,
    expected_reason,
    expected_signal,
) -> None:
    context = _Context()
    context.page.content = mock.Mock(
        return_value=html.replace(
            "</head>",
            "<meta name='authorization' content='Bearer private-secret'></head>",
        )
    )

    def goto(url: str, **_kwargs):
        context.page.url = url
        response = _Response()
        response.status = 403
        return response

    context.page.goto = goto
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1111/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    readiness_result = (
        _stable_wiley_readiness()
        if body_ready
        else SimpleNamespace(
            attempted=True,
            ready=False,
            selector="section.article-section__content",
            text_length=4200 if "article-section__content" in html else 0,
            paragraph_count=2 if "article-section__content" in html else 0,
            heading_count=1 if "article-section__content" in html else 0,
            fingerprint="unstable-wiley-body",
        )
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        lambda *_args, **_kwargs: readiness_result,
    )

    with pytest.raises(browser_runtime.BrowserRuntimeFailure) as raised:
        _playwright_browser.fetch_html_with_playwright(
            ["https://onlinelibrary.wiley.com/doi/10.1111/example"],
            publisher="wiley",
            config=config,
            wait_seconds=2,
        )

    trace = raised.value.details["trace"]
    candidate = trace["candidates"][0]
    review = candidate["http_access_status_review"]
    assert review["accepted"] is False
    assert review["candidate_confirmed"] is False
    assert review["status_override_applied"] is False
    assert review["fulltext_acceptance"] == "not_attempted"
    assert review["reason"] == expected_reason
    if expected_signal is not None:
        assert expected_signal in review["blocking_signals"]
    assert "private-secret" not in str(trace)


def test_wiley_403_failure_advances_to_next_candidate(monkeypatch, tmp_path) -> None:
    context = _Context()
    navigation_count = 0

    def goto(url: str, **_kwargs):
        nonlocal navigation_count
        navigation_count += 1
        context.page.url = url
        response = _Response()
        if navigation_count == 1:
            response.status = 403
            response.headers = {"content-type": "text/html"}
        return response

    context.page.goto = goto
    context.page.content = lambda: (
        _wiley_review_html("")
        if navigation_count == 1
        else "<html><head><title>Article</title></head><body><main>Full text</main></body></html>"
    )
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1111/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    readiness = mock.Mock(return_value=_stable_wiley_readiness())
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        readiness,
    )

    result = _playwright_browser.fetch_html_with_playwright(
        [
            "https://onlinelibrary.wiley.com/doi/10.1111/example",
            "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
        ],
        publisher="wiley",
        config=config,
        wait_seconds=2,
    )

    assert result.response_status == 200
    assert readiness.call_count == 2
    candidates = result.diagnostics["browser_runtime_trace"]["candidates"]
    assert candidates[0]["status"] == 403
    assert candidates[0]["dom_readiness_result"] == "ready"
    assert candidates[0]["http_access_status_review"]["reason"] == (
        "doi_evidence_missing"
    )
    assert candidates[1]["result"] == "success"


def test_wiley_all_http_status_candidates_fail_with_reviews(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    navigation_count = 0

    def goto(url: str, **_kwargs):
        nonlocal navigation_count
        navigation_count += 1
        context.page.url = url
        response = _Response()
        response.status = 403 if navigation_count == 1 else 401
        return response

    context.page.goto = goto
    context.page.content = mock.Mock(
        return_value=_wiley_review_html(
            "<meta name='citation_doi' content='10.1111/different'>"
        )
    )
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1111/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        lambda *_args, **_kwargs: _stable_wiley_readiness(),
    )

    with pytest.raises(browser_runtime.BrowserRuntimeFailure) as raised:
        _playwright_browser.fetch_html_with_playwright(
            [
                "https://onlinelibrary.wiley.com/doi/10.1111/example",
                "https://onlinelibrary.wiley.com/doi/full/10.1111/example",
            ],
            publisher="wiley",
            config=config,
            wait_seconds=2,
        )

    failure = raised.value
    assert failure.kind == "publisher_access_denied"
    candidates = failure.details["trace"]["candidates"]
    assert [candidate["status"] for candidate in candidates] == [403, 401]
    assert [
        candidate["http_access_status_review"]["reason"] for candidate in candidates
    ] == ["doi_mismatch", "doi_mismatch"]
    assert all(
        candidate["block_reason"] == "publisher_access_denied"
        for candidate in candidates
    )


def test_provider_resource_policy_blocks_only_configured_heavy_types(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="pnas",
        doi="10.1073/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
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
        publisher="pnas",
        config=config,
        wait_seconds=0,
        options=browser_runtime.BrowserHtmlFetchOptions(
            blocked_resource_types=frozenset({"image", "font", "media"})
        ),
    )

    routes = {}
    for resource_type in ("image", "font", "media", "stylesheet", "script", "xhr"):
        route = mock.Mock()
        route.request.resource_type = resource_type
        route.request.url = f"https://cross-origin-assets.test/{resource_type}"
        context.page.route_handler(route)
        routes[resource_type] = route
    for resource_type in ("image", "font", "media"):
        routes[resource_type].abort.assert_called_once()
        routes[resource_type].continue_.assert_not_called()
    for resource_type in ("stylesheet", "script", "xhr"):
        routes[resource_type].continue_.assert_called_once()
        routes[resource_type].abort.assert_not_called()
    assert context.route_handler is None

    trace = result.diagnostics["browser_runtime_trace"]
    assert trace["blocked_resource_types"] == ["font", "image", "media"]
    assert trace["blocked_request_count"] == 3
    assert trace["blocked_request_types"] == ["font", "image", "media"]
    assert trace["navigation_count"] == 1


def test_exact_script_response_policy_fulfills_only_matching_script(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="aip",
        doi="10.1063/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://pubs.aip.org/article"],
        publisher="aip",
        config=config,
        wait_seconds=0,
        options=browser_runtime.BrowserHtmlFetchOptions(
            empty_script_response_urls=frozenset({"https://static.adzerk.net/ados.js"})
        ),
    )

    target_script = mock.Mock()
    target_script.request.resource_type = "script"
    target_script.request.url = "https://static.adzerk.net/ados.js"
    context.page.route_handler(target_script)

    failed_target_script = mock.Mock()
    failed_target_script.request.resource_type = "script"
    failed_target_script.request.url = "https://static.adzerk.net/ados.js"
    failed_target_script.fulfill.side_effect = RuntimeError("fulfill failed")
    context.page.route_handler(failed_target_script)

    passthrough_routes = []
    for resource_type, url in (
        ("script", "https://static.adzerk.net/other.js"),
        ("xhr", "https://static.adzerk.net/ados.js"),
        ("document", "https://static.adzerk.net/ados.js"),
    ):
        route = mock.Mock()
        route.request.resource_type = resource_type
        route.request.url = url
        context.page.route_handler(route)
        passthrough_routes.append(route)

    target_script.fulfill.assert_called_once_with(
        status=200,
        content_type="application/javascript",
        body="",
    )
    target_script.continue_.assert_not_called()
    target_script.abort.assert_not_called()
    failed_target_script.continue_.assert_called_once()
    for route in passthrough_routes:
        route.continue_.assert_called_once()
        route.fulfill.assert_not_called()
        route.abort.assert_not_called()

    trace = result.diagnostics["browser_runtime_trace"]
    assert trace["empty_script_response_count"] == 1
    assert trace["blocked_request_count"] == 0


def test_pnas_body_readiness_uses_bounded_budget_and_keeps_final_html(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="pnas",
        doi="10.1073/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    captured_timeout: list[float] = []

    def body_readiness(_page, _publisher, *, timeout_seconds):
        captured_timeout.append(timeout_seconds)
        return SimpleNamespace(attempted=True, ready=False)

    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        body_readiness,
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://www.pnas.org/doi/10.1073/example"],
        publisher="pnas",
        config=config,
        wait_seconds=8,
        readiness=BrowserHtmlReadiness(wait_for_article_body=True),
        options=browser_runtime.BrowserHtmlFetchOptions(readiness_budget_seconds=8.0),
    )

    assert len(captured_timeout) == 1
    assert 0 < captured_timeout[0] <= 8.0
    assert "Full text" in result.html
    candidate = result.diagnostics["browser_runtime_trace"]["candidates"][0]
    assert candidate["dom_readiness_result"] == "timeout"


def test_unconfigured_science_fast_policy_keeps_legacy_media_only_blocking(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="science",
        doi="10.1126/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )

    _playwright_browser.fetch_html_with_playwright(
        ["https://example.test/article"],
        publisher="science",
        config=config,
        wait_seconds=0,
        disable_media=True,
    )

    routes = {}
    for resource_type in ("image", "font", "media", "stylesheet", "script", "xhr"):
        route = mock.Mock()
        route.request.resource_type = resource_type
        route.request.url = context.page.url
        context.page.route_handler(route)
        routes[resource_type] = route
    routes["media"].abort.assert_called_once()
    for resource_type in ("image", "font", "stylesheet", "script", "xhr"):
        routes[resource_type].continue_.assert_called_once()
        routes[resource_type].abort.assert_not_called()


def test_figure_page_fetches_reuse_one_runtime_context_and_page(
    monkeypatch, tmp_path
) -> None:
    browser_context = _Context()
    open_context = mock.Mock(return_value=(None, browser_context))
    monkeypatch.setattr(_playwright_browser, "open_browser_context", open_context)
    config = BrowserRuntimeConfig(
        provider="royalsocietypublishing",
        doi="10.1098/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    runtime_context = RuntimeContext(env={})
    readiness = browser_runtime.BrowserHtmlReadiness(wait_for_article_body=False)
    try:
        first = _playwright_browser.fetch_html_with_playwright(
            ["https://example.test/figure/1"],
            publisher="royalsocietypublishing",
            config=config,
            readiness=readiness,
            wait_seconds=0,
            runtime_context=runtime_context,
            options=browser_runtime.BrowserHtmlFetchOptions(reuse_runtime_page=True),
        )
        second = _playwright_browser.fetch_html_with_playwright(
            ["https://example.test/figure/2"],
            publisher="royalsocietypublishing",
            config=config,
            readiness=readiness,
            wait_seconds=0,
            runtime_context=runtime_context,
            options=browser_runtime.BrowserHtmlFetchOptions(reuse_runtime_page=True),
        )
    finally:
        runtime_context.close()

    open_context.assert_called_once()
    assert browser_context.events.count("new_page") == 1
    first_trace = first.diagnostics["browser_runtime_trace"]
    second_trace = second.diagnostics["browser_runtime_trace"]
    assert first_trace["runtime_page_reused"] is False
    assert second_trace["runtime_page_reused"] is True
    assert first_trace["runtime_page_navigation_count"] == 1
    assert second_trace["runtime_page_navigation_count"] == 2


def test_camoufox_provider_page_preparation_runs_before_html_capture(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    page_state = {"html": "<html><body><main>Before preparation</main></body></html>"}
    context.page.content = lambda: page_state["html"]

    def prepare_browser_page(page, *, timeout_ms):
        assert page is context.page
        assert timeout_ms > 0
        page_state["html"] = (
            "<html><body><main>After preparation</main>"
            '<table data-paper-fetch-hydrated-table="true"></table>'
            "</body></html>"
        )
        return {"attempted": True, "tables_hydrated": 1}

    config = BrowserRuntimeConfig(
        provider="example",
        doi="10.1234/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "publisher_profile",
        lambda _publisher: SimpleNamespace(prepare_browser_page=prepare_browser_page),
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://example.test/article"],
        publisher="example",
        config=config,
        wait_seconds=0,
    )

    assert "After preparation" in result.html
    candidate = result.diagnostics["browser_runtime_trace"]["candidates"][0]
    assert candidate["provider_page_preparation"] == {
        "attempted": True,
        "tables_hydrated": 1,
    }
    assert candidate["provider_page_preparation_seconds"] >= 0


def test_camoufox_candidate_deadline_preserves_observed_access_boundary(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    deadline_expired = False

    def challenge_content() -> str:
        nonlocal deadline_expired
        deadline_expired = True
        return (
            "<html><head><title>Just a moment...</title></head>"
            "<body>Checking your browser before accessing the site.</body></html>"
        )

    context.page.content = challenge_content
    context.page.title = lambda: "Just a moment..."
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1002/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser.time,
        "monotonic",
        lambda: 1.0 if deadline_expired else 0.0,
    )

    with pytest.raises(browser_runtime.BrowserRuntimeFailure) as raised:
        _playwright_browser.fetch_html_with_playwright(
            [
                "https://onlinelibrary.wiley.com/doi/full/10.1002/example",
                "https://onlinelibrary.wiley.com/doi/10.1002/example",
            ],
            publisher="wiley",
            config=config,
            wait_seconds=0,
            max_timeout_ms=500,
            readiness=BrowserHtmlReadiness(wait_for_article_body=False),
        )

    failure = raised.value
    assert failure.kind == "cloudflare_challenge"
    assert failure.details["candidate_deadline_failure"] == {
        "failure_code": "browser_connect_timeout",
        "message": (
            "Browser HTML request deadline was exhausted before another candidate."
        ),
    }
    assert failure.details["trace"]["deadline_exhausted"] is True
    assert len(failure.details["trace"]["candidates"]) == 1


def test_camoufox_candidate_transport_failure_preserves_observed_access_boundary(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    navigation_count = 0

    def goto(url: str, **_kwargs):
        nonlocal navigation_count
        navigation_count += 1
        context.page.url = url
        if navigation_count == 2:
            raise TimeoutError("Page.goto: Timeout 84000ms exceeded.")
        return _Response()

    context.page.goto = goto
    context.page.content = lambda: (
        "<html><head><title>Just a moment...</title></head>"
        "<body>Checking your browser before accessing the site.</body></html>"
    )
    context.page.title = lambda: "Just a moment..."
    config = BrowserRuntimeConfig(
        provider="wiley",
        doi="10.1002/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )

    with pytest.raises(browser_runtime.BrowserRuntimeFailure) as raised:
        _playwright_browser.fetch_html_with_playwright(
            [
                "https://onlinelibrary.wiley.com/doi/full/10.1002/example",
                "https://onlinelibrary.wiley.com/doi/10.1002/example",
            ],
            publisher="wiley",
            config=config,
            wait_seconds=0,
            readiness=BrowserHtmlReadiness(wait_for_article_body=False),
        )

    failure = raised.value
    assert failure.kind == "cloudflare_challenge"
    assert failure.details["subsequent_candidate_failures"] == [
        {
            "failure_code": "camoufox_request_failed",
            "message": "Page.goto: Timeout 84000ms exceeded.",
        }
    ]
    assert len(failure.details["trace"]["candidates"]) == 2
    assert failure.details["trace"]["candidates"][1]["error"] == (
        "Page.goto: Timeout 84000ms exceeded."
    )


@pytest.mark.parametrize(
    ("status", "title", "html", "final_url", "expected_reason"),
    [
        (
            403,
            "Forbidden",
            "<html><body>Forbidden</body></html>",
            "https://example.test/article",
            "http_403",
        ),
        (
            200,
            "Just a moment...",
            "<html><body>Checking your browser before accessing the site.</body></html>",
            "https://example.test/article",
            "cloudflare_challenge",
        ),
        (
            200,
            "Abstract",
            "<html><body>Abstract only</body></html>",
            "https://example.test/doi/abs/10.1000/example",
            "redirected_to_abstract",
        ),
    ],
)
def test_lightweight_warm_rejects_unusable_navigation(
    monkeypatch,
    tmp_path,
    status,
    title,
    html,
    final_url,
    expected_reason,
) -> None:
    context = _Context()

    class Response:
        headers = {"content-type": "text/html"}

        def __init__(self, response_status: int) -> None:
            self.status = response_status

        def all_headers(self):
            return dict(self.headers)

    def goto(_url: str, **_kwargs):
        context.page.url = final_url
        return Response(status)

    context.page.goto = goto
    context.page.title = lambda: title
    context.page.content = lambda: html
    config = BrowserRuntimeConfig(
        provider="example",
        doi="10.1000/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )

    result = _playwright_browser.warm_browser_context_with_playwright(
        ["https://example.test/doi/full/10.1000/example"],
        publisher="example",
        config=config,
        lightweight=True,
    )

    assert result.accepted is False
    assert result.changed is False
    assert result.status == status
    assert result.reason == expected_reason


def test_lightweight_warm_reports_no_cookie_change(monkeypatch, tmp_path) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="example",
        doi="10.1000/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )

    result = _playwright_browser.warm_browser_context_with_playwright(
        ["https://example.test/article"],
        publisher="example",
        config=config,
        lightweight=True,
    )

    assert result.accepted is True
    assert result.changed is False
    assert result.reason == "no_cookie_change"
    assert result.cookie_delta == {"added": 0, "updated": 0, "removed": 0}


def test_camoufox_figure_page_waits_for_image_selector_without_fixed_sleep(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="acs",
        doi="10.1021/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    readiness = mock.Mock()
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        readiness,
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://pubs.acs.org/view-large/figure/123/example.tif"],
        publisher="acs",
        config=config,
        wait_seconds=5,
        readiness=BrowserHtmlReadiness(
            wait_for_article_body=False,
            selector="img.content-image[src], img.content-image[data-src]",
        ),
    )

    readiness.assert_not_called()
    context.page.wait_for_selector.assert_called_once_with(
        "img.content-image[src], img.content-image[data-src]",
        state="attached",
        timeout=5000,
    )
    context.page.wait_for_timeout.assert_not_called()
    assert result.response_status == 200
    trace = result.diagnostics["browser_runtime_trace"]
    assert trace["article_body_wait_enabled"] is False
    assert trace["selector_wait_enabled"] is True
    assert trace["candidates"][0]["selector_readiness_ready"] is True


def test_camoufox_figure_page_selector_timeout_is_best_effort(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    context.page.wait_for_selector.side_effect = RuntimeError("selector timeout")
    config = BrowserRuntimeConfig(
        provider="royalsocietypublishing",
        doi="10.1098/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://royalsocietypublishing.org/view-large/figure/123/example.tif"],
        publisher="royalsocietypublishing",
        config=config,
        wait_seconds=5,
        readiness=BrowserHtmlReadiness(
            wait_for_article_body=False,
            selector="img.content-image[src], img.content-image[data-src]",
        ),
    )

    context.page.wait_for_selector.assert_called_once()
    context.page.wait_for_timeout.assert_not_called()
    assert result.response_status == 200
    trace = result.diagnostics["browser_runtime_trace"]
    assert trace["candidates"][0]["selector_readiness_attempted"] is True
    assert trace["candidates"][0]["selector_readiness_ready"] is False


def test_camoufox_figure_page_without_selector_uses_fixed_wait(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    config = BrowserRuntimeConfig(
        provider="example",
        doi="10.1234/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    body_readiness = mock.Mock()
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )
    monkeypatch.setattr(
        _playwright_browser,
        "wait_for_atypon_body_dom_ready",
        body_readiness,
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://example.test/view-large/figure/123/example.tif"],
        publisher="example",
        config=config,
        wait_seconds=2,
        readiness=BrowserHtmlReadiness(wait_for_article_body=False),
    )

    body_readiness.assert_not_called()
    context.page.wait_for_selector.assert_not_called()
    context.page.wait_for_timeout.assert_called_once_with(2000)
    assert result.response_status == 200
    trace = result.diagnostics["browser_runtime_trace"]
    assert trace["article_body_wait_enabled"] is False
    assert trace["selector_wait_enabled"] is False


def test_ieee_required_selector_waits_for_matching_article_number(
    monkeypatch, tmp_path
) -> None:
    context = _Context()
    context.page.url = "https://ieeexplore.ieee.org/document/10772041/"
    challenge_html = (
        "<html><head><script src='https://example.token.awswaf.com/challenge.js'>"
        "</script></head><body><div id='challenge-container'></div>"
        "<noscript>Verify you're not a robot.</noscript></body></html>"
    )
    context.page.content = mock.Mock(return_value=challenge_html)

    def complete_waf_challenge(_expression, *, arg, timeout):
        assert arg == {"selector": "#article", "expectedText": "10772041"}
        assert timeout == 15000
        context.page.content.return_value = (
            "<html><body><article id='article'>10772041</article></body></html>"
        )

    context.page.wait_for_function.side_effect = complete_waf_challenge
    response = SimpleNamespace(
        status=202,
        headers={
            "content-type": "text/html",
            "server": "CloudFront",
            "x-amzn-waf-action": "challenge",
        },
    )
    response.all_headers = lambda: dict(response.headers)
    context.page.goto = mock.Mock(return_value=response)
    config = BrowserRuntimeConfig(
        provider="ieee",
        doi="10.1109/TIM.2024.3509573",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, context),
    )

    result = _playwright_browser.fetch_html_with_playwright(
        ["https://ieeexplore.ieee.org/document/10772041/"],
        publisher="ieee",
        config=config,
        wait_seconds=15,
        readiness=BrowserHtmlReadiness(
            wait_for_article_body=False,
            selector="#article",
            selector_text="10772041",
            require_selector=True,
        ),
    )

    context.page.wait_for_function.assert_called_once()
    trace = result.diagnostics["browser_runtime_trace"]
    assert trace["candidates"][0]["selector_readiness_ready"] is True
    assert trace["candidates"][0]["selector_readiness_expected_text"] == "10772041"


def test_ieee_required_selector_preserves_aws_waf_timeout_diagnostic(
    monkeypatch, tmp_path
) -> None:
    browser_context = _Context()
    browser_context.page.url = "https://ieeexplore.ieee.org/document/10772041/"
    browser_context.page.wait_for_function.side_effect = RuntimeError(
        "selector timeout"
    )
    challenge_html = (
        "<html><head><title></title>"
        "<script src='https://example.token.awswaf.com/challenge.js'></script>"
        "</head><body><div id='challenge-container'></div>"
        "<noscript>JavaScript is disabled. Verify you're not a robot.</noscript>"
        "</body></html>"
    )
    browser_context.page.content = mock.Mock(return_value=challenge_html)
    browser_context.page.title = mock.Mock(return_value="")
    response = SimpleNamespace(
        status=202,
        headers={
            "content-type": "text/html",
            "server": "CloudFront",
            "x-amzn-waf-action": "challenge",
        },
    )
    response.all_headers = lambda: dict(response.headers)
    browser_context.page.goto = mock.Mock(return_value=response)
    config = BrowserRuntimeConfig(
        provider="ieee",
        doi="10.1109/TIM.2024.3509573",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
        persist_storage_state=False,
    )
    runtime = RuntimeContext(
        env={},
        download_dir=tmp_path,
        artifact_mode="all",
    )
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        lambda *_args, **_kwargs: (None, browser_context),
    )
    try:
        with pytest.raises(browser_runtime.BrowserRuntimeFailure) as raised:
            _playwright_browser.fetch_html_with_playwright(
                ["https://ieeexplore.ieee.org/document/10772041/"],
                publisher="ieee",
                config=config,
                wait_seconds=15,
                readiness=BrowserHtmlReadiness(
                    wait_for_article_body=False,
                    selector="#article",
                    selector_text="10772041",
                    require_selector=True,
                ),
                runtime_context=runtime,
            )

        failure = raised.value
        assert failure.kind == "aws_waf_challenge"
        assert failure.details["challenge_provider"] == "aws_waf"
        assert failure.details["response_status"] == 202
        diagnostic = failure.details["failure_diagnostic"]
        assert diagnostic["raw_html"]["byte_count"] > 0
        assert diagnostic["page_summary"] is None
        assert diagnostic["diagnostic_path"]
    finally:
        runtime.close()


def test_aip_normal_load_does_not_register_routes(monkeypatch, tmp_path):
    from paper_fetch.providers.aip import AIP_BROWSER_PROFILE

    context = _Context()
    monkeypatch.setattr(
        _playwright_browser, "open_browser_context", lambda *a, **k: (None, context)
    )
    profile = AIP_BROWSER_PROFILE
    _playwright_browser.fetch_html_with_playwright(
        ["https://pubs.aip.org/doi/10.1063/example"],
        publisher="aip",
        config=BrowserRuntimeConfig(
            provider="aip",
            doi="10.1063/example",
            artifact_dir=tmp_path,
            headless=True,
            user_agent=None,
            persist_storage_state=False,
        ),
        wait_seconds=0,
        disable_media=profile.fast_html_attempt,
        options=browser_runtime.BrowserHtmlFetchOptions(
            blocked_resource_types=profile.blocked_resource_types or None,
            empty_script_response_urls=profile.empty_script_response_urls,
        ),
    )
    assert context.page.route_handler is None
    assert context.route_handler is None


@pytest.mark.parametrize("provider", ["pnas", "science"])
def test_pnas_sidebar_route_is_exact_and_provider_local(
    monkeypatch, tmp_path, provider
):
    context = _Context()
    monkeypatch.setattr(
        _playwright_browser, "open_browser_context", lambda *a, **k: (None, context)
    )
    result = _playwright_browser.fetch_html_with_playwright(
        ["https://www.pnas.org/doi/10.1073/example"],
        publisher=provider,
        config=BrowserRuntimeConfig(
            provider=provider,
            doi="10.1073/example",
            artifact_dir=tmp_path,
            headless=True,
            user_agent=None,
            persist_storage_state=False,
        ),
        wait_seconds=0,
        disable_media=True,
    )
    target = "https://www.pnas.org/pb/widgets/fullSideBarMetric/getResponse"
    for url, resource_type, blocked in (
        (target, "xhr", True),
        (target + "?article=/doi/10.1073/example", "fetch", True),
        (target + "/extra", "xhr", False),
        (target.replace("www.pnas.org", "other.test"), "xhr", False),
        ("https://www.pnas.org/doi/10.1073/example", "document", False),
        ("https://www.pnas.org/login", "xhr", False),
        ("https://www.pnas.org/mathjax.js", "script", False),
        ("https://www.pnas.org/image.png", "image", False),
        ("https://www.pnas.org/references", "fetch", False),
    ):
        route = mock.Mock()
        route.request.url = url
        route.request.resource_type = resource_type
        context.page.route_handler(route)
        assert route.abort.called == (blocked and provider == "pnas")
        assert route.continue_.called != (blocked and provider == "pnas")
    trace = result.diagnostics["browser_runtime_trace"]
    assert trace.get("blocked_sidebar_metrics_count", 0) == (
        2 if provider == "pnas" else 0
    )


@pytest.mark.parametrize(
    "scenario",
    [
        "replaced",
        "denied",
        "iframe",
        "different_doi",
        "unrelated",
        "unfinished",
        "isolation",
    ],
)
def test_science_final_document_response_ownership(monkeypatch, tmp_path, scenario):
    context = _Context()
    page = context.page
    page.main_frame = object()
    listeners = {}
    page.on = lambda event, callback: listeners.setdefault(event, []).append(callback)
    page.remove_listener = lambda event, callback: listeners[event].remove(callback)

    def emit(event, value):
        for callback in list(listeners.get(event, [])):
            callback(value)

    def response(status, url, *, main=True, finished=True):
        request = SimpleNamespace(
            url=url,
            resource_type="document",
            frame=page.main_frame if main else object(),
            is_navigation_request=lambda: True,
        )
        result = SimpleNamespace(
            url=url,
            request=request,
            status=status,
            headers={"content-type": "text/html", "x-document-status": str(status)},
        )
        emit("request", request)
        emit("response", result)
        if finished:
            emit("requestfinished", request)
        return result

    count = 0
    url = "https://www.science.org/doi/full/10.1126/example"

    def goto(target, **kwargs):
        nonlocal count
        count += 1
        page.url = target
        return response(403, target)

    page.goto = goto

    def readiness(*args, **kwargs):
        if scenario == "denied" or (scenario == "isolation" and count == 2):
            return
        target = page.url
        if scenario == "different_doi":
            target = "https://www.science.org/doi/full/10.1126/different"
            page.url = target
        if scenario == "unrelated":
            target = "https://other.test/doi/full/10.1126/example"
            page.url = target
        response(
            200, target, main=scenario != "iframe", finished=scenario != "unfinished"
        )

    monkeypatch.setattr(
        _playwright_browser, "_wait_for_browser_html_readiness", readiness
    )
    monkeypatch.setattr(
        _playwright_browser, "open_browser_context", lambda *a, **k: (None, context)
    )
    if scenario == "isolation":
        page.title = lambda: "Just a moment..." if count == 1 else "Article"
        page.content = lambda: (
            "<html><body>Just a moment... Verify you are human</body></html>"
            if count == 1
            else "<html><body><main>Full text</main></body></html>"
        )
    kwargs = dict(
        publisher="science",
        config=BrowserRuntimeConfig(
            provider="science",
            doi="10.1126/example",
            artifact_dir=tmp_path,
            headless=True,
            user_agent=None,
            persist_storage_state=False,
        ),
        wait_seconds=0,
    )
    if scenario == "replaced":
        result = _playwright_browser.fetch_html_with_playwright([url], **kwargs)
        assert result.response_status == 200
        assert result.response_headers["x-document-status"] == "200"
        trace = result.diagnostics["browser_runtime_trace"]
        assert [
            item["status"] for item in trace["page_events"]["document_requests"]
        ] == [403, 200]
        assert trace["navigation_count"] == 1
    else:
        with pytest.raises(browser_runtime.BrowserRuntimeFailure):
            _playwright_browser.fetch_html_with_playwright(
                [url, url] if scenario == "isolation" else [url], **kwargs
            )
        if scenario == "isolation":
            assert count == 2
    assert all(not callbacks for callbacks in listeners.values())
