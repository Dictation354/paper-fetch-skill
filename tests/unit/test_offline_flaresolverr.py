"""Installer prerequisite and preparation contracts with boundary mocks."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from paper_fetch import offline_flaresolverr as flare, offline_setup as wizard
from paper_fetch.providers.browser_runtime.chrome import SystemChrome


@pytest.fixture
def setup(tmp_path, monkeypatch):
    setup = wizard.Setup(tmp_path, tmp_path / "offline.env")
    setup.env = {"XDG_DATA_HOME": str(tmp_path / "data")}
    monkeypatch.setattr(flare, "supported_platform", lambda: True)
    monkeypatch.setattr(flare.sys, "platform", "linux")
    monkeypatch.setattr(flare, "find_spec", lambda _: object())
    monkeypatch.setattr(
        flare, "discover_chrome", lambda _: SystemChrome("/chrome", "156.0.1.2")
    )
    monkeypatch.setattr(flare, "linux_missing", lambda *_: {})
    monkeypatch.setattr(flare, "linux_launch_prefix", lambda *_: [])
    return setup


def test_prepares_shared_cache_then_checks_with_separate_budget(setup, monkeypatch):
    calls = []
    monkeypatch.setattr(
        flare.preparation,
        "prepare_source",
        lambda cache, budget: calls.append((cache, budget)) or Path("/source"),
    )
    monkeypatch.setattr(
        flare.preparation,
        "prepare_driver",
        lambda cache, version, budget: (
            calls.append((cache, budget)) or (Path("/driver"), "156.0.1.1")
        ),
    )
    check = Mock()
    monkeypatch.setattr(flare, "local_check", check)
    flare.prepare(setup, interactive=False)
    assert calls[0][0] == Path(setup.env["XDG_DATA_HOME"]) / "paper-fetch/flaresolverr"
    assert calls[0][1] is calls[1][1]
    assert 590 < calls[0][1].remaining() <= 600
    assert check.call_args.args[1:] == (
        SystemChrome("/chrome", "156.0.1.2"),
        Path("/source"),
        Path("/driver"),
        "156.0.1.1",
    )
    assert "FlareSolverr: ready" in setup.summary()


@pytest.mark.parametrize(
    "failure", [KeyboardInterrupt(), OSError("SECRET"), EOFError()]
)
def test_failure_keeps_core_and_does_not_launch(setup, monkeypatch, failure):
    monkeypatch.setattr(flare.preparation, "prepare_source", Mock(side_effect=failure))
    check = Mock()
    monkeypatch.setattr(flare, "local_check", check)
    flare.prepare(setup, interactive=False)
    assert "FlareSolverr: not ready" in setup.summary()
    assert "SECRET" not in setup.summary()
    check.assert_not_called()


@pytest.mark.parametrize(
    "interactive,accept,success",
    [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, True, True),
    ],
)
def test_missing_dependencies_accept_decline_failure_and_noninteractive(
    setup,
    monkeypatch,
    interactive,
    accept,
    success,
):
    missing = {"Xvfb": ("xvfb",)}
    installed = []
    monkeypatch.setattr(
        flare, "linux_missing", lambda *_: {} if installed and success else missing
    )
    monkeypatch.setattr(wizard, "apt_supported", lambda: True)
    monkeypatch.setattr(wizard, "apt_package", lambda _: "xvfb")
    confirm = Mock(return_value=accept)
    monkeypatch.setattr(wizard, "confirm", confirm)
    monkeypatch.setattr(
        setup, "install_packages", lambda label, command: installed.append(command)
    )
    source = Mock(side_effect=OSError())
    monkeypatch.setattr(flare.preparation, "prepare_source", source)
    flare.prepare(setup, interactive=interactive)
    assert bool(installed) == (interactive and accept)
    assert confirm.call_count == int(interactive)
    assert source.call_count == int(interactive and accept and success)
    assert "sudo apt-get install -- xvfb" in setup.summary()


@pytest.mark.parametrize("candidate", ["google-chrome-stable", None])
@pytest.mark.parametrize(
    "interactive,accept", [(False, False), (True, False), (True, True)]
)
def test_chrome_apt_or_official_deb_needs_consent(
    setup, monkeypatch, candidate, interactive, accept
):
    monkeypatch.setattr(wizard, "apt_supported", lambda: True)
    monkeypatch.setattr(wizard, "apt_package", lambda _: candidate)
    confirm = Mock(return_value=accept)
    monkeypatch.setattr(wizard, "confirm", confirm)
    download = Mock(side_effect=lambda url, path, budget: path.write_bytes(b"deb"))
    monkeypatch.setattr(flare.preparation, "download", download)
    install = Mock()
    monkeypatch.setattr(setup, "install_packages", install)
    flare.install_linux_chrome(setup, interactive=interactive)
    selected = interactive and accept
    assert install.call_count == int(selected)
    assert download.call_count == int(selected and not candidate)
    assert confirm.call_count == int(interactive)
    if selected:
        command = install.call_args.args[1]
        assert command[:4] == ["sudo", "apt-get", "install", "--"]
        if candidate:
            assert command[4] == candidate
        else:
            assert download.call_args.args[0] == flare.CHROME_DEB_URL
            assert not Path(command[4]).exists()


def test_invalid_explicit_path_never_installs_chrome(setup, monkeypatch):
    setup.env[flare.CHROME_ENV] = "/invalid"
    monkeypatch.setattr(flare, "discover_chrome", Mock(side_effect=ValueError()))
    install = Mock()
    monkeypatch.setattr(flare, "install_linux_chrome", install)
    flare.prepare(setup, interactive=True)
    install.assert_not_called()
    assert "Correct explicit PAPER_FETCH_CHROME_BINARY_PATH" in setup.summary()


def test_windows_missing_chrome_only_provides_official_link(setup, monkeypatch):
    monkeypatch.setattr(flare.sys, "platform", "win32")
    monkeypatch.setattr(flare, "discover_chrome", Mock(side_effect=ValueError()))
    confirm = Mock(side_effect=AssertionError("must not prompt"))
    monkeypatch.setattr(wizard, "confirm", confirm)
    flare.prepare(setup, interactive=True)
    assert "https://www.google.com/chrome/" in setup.summary()
    assert "FlareSolverr: not ready" in setup.summary()


def test_namespace_failure_is_not_reported_ready(setup, monkeypatch):
    monkeypatch.setattr(
        flare,
        "linux_launch_prefix",
        Mock(
            side_effect=flare.BrowserRuntimeFailure(
                "flaresolverr_not_prepared",
                "Rootless bubblewrap namespaces are unavailable",
            )
        ),
    )
    flare.prepare(setup, interactive=False)
    assert "namespaces are unavailable" in setup.summary()
    assert "FlareSolverr: not ready" in setup.summary()


def test_other_linux_lists_missing_libraries_without_apt(setup, monkeypatch):
    monkeypatch.setattr(wizard, "apt_supported", lambda: False)
    flare.install_linux_dependencies(
        setup, {"libnss3.so": ("libnss3",)}, interactive=True
    )
    flare.install_linux_chrome(setup, interactive=True)
    assert "package manager to provide: libnss3.so" in setup.summary()
    assert "https://www.google.com/chrome/" in setup.summary()


def test_macos_skips_before_dependency_probe(setup, monkeypatch):
    monkeypatch.setattr(flare, "supported_platform", lambda: False)
    monkeypatch.setattr(flare, "find_spec", Mock(side_effect=AssertionError()))
    flare.prepare(setup, interactive=False)
    assert "FlareSolverr: skipped" in setup.summary()


def test_independent_mode_runs_noninteractively_and_respects_config(
    tmp_path, monkeypatch
):
    env_file = tmp_path / "external.env"
    env_file.write_text("PAPER_FETCH_BROWSER_HEADLESS=false\nELSEVIER_API_KEY=SECRET\n")
    result = tmp_path / "result.txt"
    runtime = tmp_path / (
        "runtime/python.exe" if wizard.os.name == "nt" else "runtime/paper-fetch-python"
    )
    runtime.parent.mkdir()
    runtime.touch()
    calls = []
    monkeypatch.delenv("PAPER_FETCH_BROWSER_HEADLESS", raising=False)
    monkeypatch.setattr(
        flare, "prepare", lambda setup, **kw: calls.append((setup.env.copy(), kw))
    )
    assert (
        wizard.main(
            [
                "--install-root",
                str(tmp_path),
                "--env-file",
                str(env_file),
                "--prepare-flaresolverr",
                "--non-interactive",
                "--result",
                str(result),
            ]
        )
        == 0
    )
    assert calls[0][1] == {"interactive": False, "system_dependencies": False}
    assert not flare.headless_mode(calls[0][0])
    assert (
        "Retry:" in result.read_text()
        and "--prepare-browsers flaresolverr" in result.read_text()
    )
    assert "SECRET" not in result.read_text()
    assert str(runtime) in result.read_text()
    assert "SECRET" in env_file.read_text()


def test_missing_playwright_reports_reinstall_command(setup, monkeypatch):
    monkeypatch.setattr(flare, "find_spec", lambda _: None)
    flare.prepare(setup, interactive=False)
    assert "Missing Playwright" in setup.summary()


@pytest.mark.parametrize(
    "failure", [None, RuntimeError("script failed"), KeyboardInterrupt()]
)
def test_local_check_uses_temporary_state_and_always_closes(
    setup, monkeypatch, failure
):
    page = SimpleNamespace(goto=Mock(), wait_for_function=Mock(side_effect=failure))
    context = SimpleNamespace(route=Mock(), new_page=lambda: page)
    manager = SimpleNamespace(
        new_context=Mock(return_value=context),
        close=Mock(),
        budget=flare.preparation.PreparationBudget(120),
    )
    configs = []

    def owner(config, **kwargs):
        configs.append(config)
        assert kwargs == {"local_check": True}
        return manager

    monkeypatch.setattr(flare, "FlareSolverrManager", owner)
    if failure:
        with pytest.raises(type(failure)):
            flare.local_check(
                setup.env,
                SystemChrome("/chrome", "156.0.1.2"),
                Path("/source"),
                Path("/driver"),
                "156",
            )
    else:
        flare.local_check(
            setup.env,
            SystemChrome("/chrome", "156.0.1.2"),
            Path("/source"),
            Path("/driver"),
            "156",
        )
    config = configs[0]
    assert config.storage_state_path is None and not config.persist_storage_state
    assert config.timeout_ms == 120000 and not config.user_data_dir.exists()
    assert page.goto.call_args.args == ("about:blank",)
    assert page.wait_for_function.call_args.args == ("() => 1 + 1 === 2",)
    assert 0 < page.wait_for_function.call_args.kwargs["timeout"] <= 120000
    manager.close.assert_called_once()


@pytest.mark.parametrize("headless", [True, False])
def test_linux_detects_shared_libraries_and_headless_socket_dependencies(
    tmp_path,
    monkeypatch,
    headless,
):
    setup = wizard.Setup(tmp_path, tmp_path / "offline.env")
    monkeypatch.setattr(
        wizard,
        "library_status",
        lambda name: "missing" if name == "libnss3.so" else "ready",
    )
    monkeypatch.setattr(flare.shutil, "which", lambda _: None)
    monkeypatch.setattr(flare, "Path", lambda _: SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(flare.os, "access", lambda *_: False)
    missing = flare.linux_missing(setup, headless)
    assert missing["libnss3.so"] == ("libnss3",)
    assert ("Xvfb" in missing) == headless
    assert ("bubblewrap (read-only X11 sockets)" in missing) == headless


@pytest.mark.parametrize("supported", [False, True])
@pytest.mark.parametrize("selection", ["all", "camoufox", "flaresolverr"])
@pytest.mark.parametrize(
    "outcome", ["ready", "partial", "cancelled", "missing", "exception"]
)
def test_browser_overall_status_and_retry_follow_selected_backends(
    tmp_path, monkeypatch, supported, selection, outcome
):
    from paper_fetch import offline_browsers

    monkeypatch.setattr(offline_browsers, "supported_platform", lambda: supported)
    monkeypatch.setattr(flare, "supported_platform", lambda: supported)
    monkeypatch.setattr(offline_browsers.sys, "platform", "darwin")
    result = tmp_path / "result.txt"

    def camoufox(setup, **kwargs):
        if outcome == "cancelled":
            raise KeyboardInterrupt
        if outcome == "exception":
            raise OSError("secret")
        if outcome != "missing":
            setup.report("Camoufox", "ready" if outcome == "ready" else "failed")

    def flaresolverr(setup, **kwargs):
        if outcome != "missing":
            setup.report("FlareSolverr", "ready")

    monkeypatch.setattr(wizard.Setup, "browser", camoufox)
    monkeypatch.setattr(flare, "prepare", flaresolverr)
    assert (
        wizard.main(
            [
                "--install-root",
                str(tmp_path),
                "--prepare-browsers",
                selection,
                "--non-interactive",
                "--result",
                str(result),
            ]
        )
        == 0
    )
    summary = result.read_text()
    if selection == "flaresolverr" and not supported:
        expected = "skipped"
    elif outcome == "ready" or (selection == "flaresolverr" and outcome != "missing"):
        expected = "ready"
    else:
        expected = "not ready"
    assert summary.splitlines()[0] == f"Browser preparation: {expected}"
    assert ("Retry:" in summary) == (expected == "not ready")
    assert "Core installation preserved" in summary
    assert "secret" not in summary
    if expected == "not ready":
        assert f"--prepare-browsers {selection}" in summary
        assert str(tmp_path / "offline.env") in summary
    if (
        selection == "all"
        and supported
        and outcome in {"cancelled", "exception", "partial"}
    ):
        assert "FlareSolverr: ready" in summary


def test_python_check_finishes_with_ready_or_unsupported(setup, monkeypatch):
    monkeypatch.setattr(flare.platform, "python_implementation", lambda: "PyPy")
    flare.prepare(setup, interactive=False)
    assert "Python: unsupported" in setup.summary()
    assert "Python: checking" not in setup.summary()


def test_shared_preparation_rechecks_dependencies_without_second_install(
    setup, monkeypatch
):
    from paper_fetch import offline_browsers

    installed = []
    monkeypatch.setattr(offline_browsers, "supported_platform", lambda: True)
    monkeypatch.setattr(
        wizard,
        "library_status",
        lambda name: "ready" if installed or name != "libgtk-3.so.0" else "missing",
    )
    monkeypatch.setattr(wizard, "apt_supported", lambda: True)
    monkeypatch.setattr(wizard, "apt_package", lambda names: names[0])
    monkeypatch.setattr(wizard, "confirm", lambda _: True)
    monkeypatch.setattr(setup, "install_packages", lambda *args: installed.append(args))
    monkeypatch.setattr(
        setup, "browser", lambda **kw: setup.report("Camoufox", "ready")
    )
    prepare = Mock(
        side_effect=lambda setup, **kw: setup.report("FlareSolverr", "ready")
    )
    monkeypatch.setattr(flare, "prepare", prepare)
    offline_browsers.prepare(setup, selection="all", interactive=True)
    assert len(installed) == 1
    assert prepare.call_args.kwargs == {
        "interactive": True,
        "system_dependencies": False,
    }
    assert "libgtk-3.so.0: ready" in setup.summary()
    assert "missing" not in setup.summary()
    assert "installation available" not in setup.summary()
