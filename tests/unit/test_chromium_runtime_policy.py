"""PNAS backend policy, isolated preparation and static probe boundary contracts."""

from dataclasses import replace

import pytest

from paper_fetch import browser_runtime_policy as policy
from paper_fetch.providers.browser_runtime.api import load_runtime_config
from paper_fetch.providers.browser_runtime.types import (
    BrowserRuntimeConfig,
    BrowserRuntimeFailure,
)


@pytest.mark.parametrize(
    "system,machine,backend",
    [
        ("linux", "x86_64", "scrapling"),
        ("win32", "AMD64", "scrapling"),
        ("darwin", "arm64", "scrapling"),
        ("darwin", "x86_64", "scrapling"),
        ("linux", "aarch64", "scrapling"),
    ],
)
def test_platforms_share_scrapling_and_chromium(monkeypatch, system, machine, backend):
    monkeypatch.setattr(policy.sys, "platform", system)
    monkeypatch.setattr(policy.platform, "machine", lambda: machine)
    assert policy.selected_backend({}, provider="pnas") == backend
    assert policy.engine_name() == "chromium"
    assert (
        policy.selected_backend(
            {"PAPER_FETCH_PNAS_BROWSER_BACKEND": "scrapling"}, provider="wiley"
        )
        == "scrapling"
    )
    assert (
        policy.selected_backend(
            {"PAPER_FETCH_PNAS_BROWSER_BACKEND": "chromium"}, provider="pnas"
        )
        == "scrapling"
    )


def test_backend_is_fixed_and_ignores_removed_selector():
    assert policy.selected_backend({}, provider="pnas") == "scrapling"


def test_configuration_uses_native_profile(tmp_path):
    config = load_runtime_config(
        {"PAPER_FETCH_BROWSER_PROFILE_DIR": str(tmp_path)}, provider="pnas", doi="test"
    )
    assert config.profile_dir == tmp_path / "chromium"


def test_solver_error_survives_candidate_deadline():
    from paper_fetch.providers.browser_runtime.html_fetcher import (
        _candidate_deadline_failure,
    )

    failure = BrowserRuntimeFailure(
        "scrapling_navigation_failed", "Cloudflare denied the request"
    )
    assert (
        _candidate_deadline_failure(failure, trace={"backend": "scrapling"}).kind
        == "browser_connect_timeout"
    )
    assert failure.message == "Cloudflare denied the request"


@pytest.mark.parametrize("backend,mode", [("scrapling", "page_click")])
def test_pnas_attachment_mode_uses_its_actual_backend(tmp_path, backend, mode):
    from paper_fetch.providers.pnas import PnasClient

    client = PnasClient(object(), {})
    captured = []
    client.deps = replace(
        client.deps,
        _build_shared_browser_file_fetcher=lambda **kwargs: captured.append(kwargs),
    )
    config = BrowserRuntimeConfig(
        "pnas",
        "10.1073/test",
        tmp_path,
        True,
        None,
        backend="scrapling",
    )
    client._browser_asset_file_fetcher(
        object(),
        attempt_supplementary_assets=True,
        browser_config=config,
        browser_context_seed_getter=lambda: {},
        seed_urls_getter=lambda: [],
        browser_user_agent=None,
        headless=True,
    )
    assert captured[0]["browser_options"].file_fetch_mode == mode
    assert captured[0]["browser_options"].runtime_config is config
    assert captured[0]["use_runtime_shared_browser"] is True
