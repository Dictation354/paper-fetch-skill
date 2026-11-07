"""Managed component preparation and independent installer boundary contracts."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from paper_fetch import offline_byparr as byparr, offline_setup as wizard


@pytest.fixture
def setup(tmp_path, monkeypatch):
    setup = wizard.Setup(tmp_path, tmp_path / "offline.env")
    setup.env = {"XDG_DATA_HOME": str(tmp_path / "data")}
    monkeypatch.setattr(byparr, "supported_platform", lambda: True)
    monkeypatch.setattr(
        byparr.DEFAULT_BYPARR_BACKEND, "ensure_runtime_ready", lambda _: None
    )
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager._launch_executable_path",
        lambda _: None,
    )
    return setup


def test_prepares_shared_cache_then_checks_with_separate_budget(setup, monkeypatch):
    prepare = Mock(return_value=Path("/source"))
    monkeypatch.setattr(byparr.preparation, "prepare_components", prepare)
    check = Mock()
    monkeypatch.setattr(byparr, "local_check", check)
    byparr.prepare(setup, interactive=False)
    cache, budget = prepare.call_args.args
    assert cache == Path(setup.env["XDG_DATA_HOME"]) / "paper-fetch/byparr"
    assert 590 < budget.remaining() <= 600
    assert check.call_args.args == (setup.env, Path("/source"))
    assert "Byparr: ready" in setup.summary()


@pytest.mark.parametrize(
    "failure", [KeyboardInterrupt(), OSError("SECRET"), EOFError()]
)
def test_failure_keeps_core_and_does_not_launch(setup, monkeypatch, failure):
    monkeypatch.setattr(
        byparr.preparation, "prepare_components", Mock(side_effect=failure)
    )
    check = Mock()
    monkeypatch.setattr(byparr, "local_check", check)
    byparr.prepare(setup, interactive=False)
    assert "Byparr: not ready" in setup.summary()
    assert "SECRET" not in setup.summary()
    check.assert_not_called()


@pytest.mark.parametrize(
    "args", [["--prepare-flaresolverr"], ["--prepare-browsers", "flaresolverr"]]
)
def test_removed_options_report_migration(tmp_path, capsys, args):
    with pytest.raises(SystemExit) as error:
        wizard.main(["--install-root", str(tmp_path), *args])
    assert error.value.code == 2
    assert "use --prepare-byparr" in capsys.readouterr().err


def test_independent_mode_preserves_env_and_reports_retry(tmp_path, monkeypatch):
    env_file = tmp_path / "external.env"
    env_file.write_text("PAPER_FETCH_BROWSER_HEADLESS=false\nELSEVIER_API_KEY=SECRET\n")
    result = tmp_path / "result.txt"
    monkeypatch.setattr(
        byparr, "prepare", lambda setup, **kw: setup.report("Byparr", "not ready")
    )
    assert (
        wizard.main(
            [
                "--install-root",
                str(tmp_path),
                "--env-file",
                str(env_file),
                "--prepare-byparr",
                "--non-interactive",
                "--result",
                str(result),
            ]
        )
        == 0
    )
    assert "--prepare-browsers byparr" in result.read_text()
    assert "SECRET" not in result.read_text()
    assert "SECRET" in env_file.read_text()


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
        budget=byparr.preparation.PreparationBudget(120),
    )
    configs = []

    def owner(config, **kwargs):
        configs.append(config)
        assert kwargs == {"local_check": True}
        return manager

    monkeypatch.setattr(byparr, "ByparrManager", owner)
    if failure:
        with pytest.raises(type(failure)):
            byparr.local_check(setup.env, Path("/source"))
    else:
        byparr.local_check(setup.env, Path("/source"))
    config = configs[0]
    assert config.storage_state_path is None and not config.persist_storage_state
    assert config.timeout_ms == 120000 and not config.user_data_dir.exists()
    assert page.goto.call_args.args == ("about:blank",)
    assert 0 < page.wait_for_function.call_args.kwargs["timeout"] <= 120000
    manager.close.assert_called_once()


@pytest.mark.parametrize("supported", [False, True])
@pytest.mark.parametrize("selection", ["all", "camoufox", "byparr"])
@pytest.mark.parametrize(
    "outcome", ["ready", "partial", "cancelled", "missing", "exception"]
)
def test_browser_overall_status_and_retry_follow_selected_backends(
    tmp_path, monkeypatch, supported, selection, outcome
):
    from paper_fetch import offline_browsers

    monkeypatch.setattr(byparr, "supported_platform", lambda: supported)
    monkeypatch.setattr(offline_browsers.sys, "platform", "darwin")
    result = tmp_path / "result.txt"

    def camoufox(setup, **kwargs):
        if outcome == "cancelled":
            raise KeyboardInterrupt
        if outcome == "exception":
            raise OSError("secret")
        if outcome != "missing":
            setup.report("Camoufox", "ready" if outcome == "ready" else "failed")

    def prepare_byparr(setup, **kwargs):
        if outcome == "cancelled":
            raise KeyboardInterrupt
        if outcome == "exception":
            raise OSError("secret")
        if outcome != "missing":
            setup.report("Byparr", "ready" if outcome == "ready" else "not ready")

    monkeypatch.setattr(wizard.Setup, "browser", camoufox)
    monkeypatch.setattr(byparr, "prepare", prepare_byparr)
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
    expected = "ready" if outcome == "ready" else "not ready"
    assert summary.splitlines()[0] == f"Browser preparation: {expected}"
    assert ("Retry:" in summary) == (expected == "not ready")
    assert "Core installation preserved" in summary
    assert "secret" not in summary
    if expected == "not ready":
        assert f"--prepare-browsers {selection}" in summary
        assert str(tmp_path / "offline.env") in summary


def test_shared_preparation_rechecks_dependencies_without_second_install(
    setup, monkeypatch
):
    from paper_fetch import offline_browsers

    installed = []
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
    prepare = Mock(side_effect=lambda setup, **kw: setup.report("Byparr", "ready"))
    monkeypatch.setattr(byparr, "prepare", prepare)
    offline_browsers.prepare(setup, selection="all", interactive=True)
    assert len(installed) == 1
    assert prepare.call_args.kwargs == {
        "interactive": True,
        "system_dependencies": False,
    }
    assert "libgtk-3.so.0: ready" in setup.summary()
    assert "missing" not in setup.summary()
    assert "installation available" not in setup.summary()
