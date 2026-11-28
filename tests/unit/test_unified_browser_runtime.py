"""Selection/state contracts and the private solver boundary, without browsers."""

import pytest

from paper_fetch.provider_catalog import (
    ordered_provider_specs,
    provider_has_browser_route,
)
from paper_fetch.providers.browser_runtime.api import load_runtime_config

PROVIDERS = [
    spec.name
    for spec in ordered_provider_specs()
    if provider_has_browser_route(spec.name)
]


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(
    "system,machine",
    [
        ("linux", "x86_64"),
        ("win32", "AMD64"),
        ("darwin", "arm64"),
        ("darwin", "x86_64"),
        ("linux", "aarch64"),
    ],
)
def test_all_providers_share_backend_but_keep_state_binding(
    monkeypatch, tmp_path, provider, system, machine
):
    config = load_runtime_config(
        {
            "XDG_DATA_HOME": str(tmp_path),
        },
        provider=provider,
        doi="test",
    )
    assert config.backend == "scrapling"
    assert config.user_data_dir.name == "chromium"
    assert config.user_data_dir.parent.name == provider
    assert config.user_data_dir.parent.parent.name == "publisher-browser-profiles"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_native_overrides_stay_bound_without_migration(tmp_path, provider):
    config = load_runtime_config(
        {
            f"PAPER_FETCH_{provider.upper()}_BROWSER_BACKEND": "chromium",
            "PAPER_FETCH_BROWSER_PROFILE_DIR": str(tmp_path / "profile"),
            "PAPER_FETCH_BROWSER_USER_DATA_DIR": str(tmp_path / "data"),
        },
        provider=provider,
        doi="test",
    )
    assert config.profile_dir == tmp_path / "profile" / "chromium"
    assert config.user_data_dir == tmp_path / "data" / "chromium"
    assert not list(tmp_path.iterdir())
