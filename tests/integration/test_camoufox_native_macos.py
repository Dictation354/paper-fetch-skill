from __future__ import annotations

import json
import os
import platform
from pathlib import Path

import pytest
from browserforge.fingerprints import Screen

from paper_fetch.providers.browser_runtime.camoufox_manager import (
    CamoufoxBrowserManager,
    CamoufoxPersistentContextManager,
)


NATIVE_CAMOUFOX_TEST_ENV = "PAPER_FETCH_RUN_NATIVE_CAMOUFOX_TEST"


def _prepared_managed_install() -> tuple[Path, Path]:
    install_dir = Path.home() / "Library" / "Caches" / "camoufox"
    assert install_dir.is_absolute()
    assert not install_dir.is_symlink()
    assert install_dir.is_dir(), "run `python -m camoufox fetch` first"

    compat_flag = install_dir / ".0.5_FLAG"
    config_file = install_dir / "config.json"
    browsers_dir = install_dir / "browsers"
    assert compat_flag.is_file(), "refusing to call Camoufox on an unmanaged cache"
    assert config_file.is_file()
    assert browsers_dir.is_dir()

    config = json.loads(config_file.read_text(encoding="utf-8"))
    active_version = config.get("active_version")
    assert isinstance(active_version, str) and active_version
    active_path = (install_dir / active_version).resolve(strict=True)
    assert active_path.is_relative_to(browsers_dir.resolve(strict=True))
    assert (active_path / "version.json").is_file()
    return install_dir, active_path


@pytest.mark.browser
def test_prepared_official_camoufox_bundle_launches_both_context_modes(
    monkeypatch,
    tmp_path,
) -> None:
    if os.environ.get(NATIVE_CAMOUFOX_TEST_ENV) != "1":
        pytest.skip(
            f"set {NATIVE_CAMOUFOX_TEST_ENV}=1 after `python -m camoufox fetch`"
        )
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        pytest.skip("native Camoufox bundle evidence requires Darwin arm64")

    import camoufox.addons as camoufox_addons
    import camoufox.sync_api as camoufox_sync_api
    from camoufox import DefaultAddons, multiversion, pkgman

    install_dir, expected_runtime_path = _prepared_managed_install()
    # Global pytest policy isolates XDG_CACHE_HOME. Point only this opt-in
    # native process at the fixed managed cache. The ownership/config checks
    # above happen before Camoufox can clean an incompatible install directory.
    monkeypatch.setattr(pkgman, "INSTALL_DIR", install_dir)
    monkeypatch.setattr(multiversion, "INSTALL_DIR", install_dir)
    monkeypatch.setattr(multiversion, "BROWSERS_DIR", install_dir / "browsers")
    monkeypatch.setattr(multiversion, "CONFIG_FILE", install_dir / "config.json")
    monkeypatch.setattr(
        multiversion, "REPO_CACHE_FILE", install_dir / "repo_cache.json"
    )
    monkeypatch.setattr(multiversion, "COMPAT_FLAG", install_dir / ".0.5_FLAG")

    # This gate proves the explicitly staged bundle, independent of new releases.
    # Launch-time preparation still runs, with discovery limited to this asset.
    version_data = json.loads((expected_runtime_path / "version.json").read_text())
    staged_version = pkgman.AvailableVersion(
        version=pkgman.Version.from_path(expected_runtime_path),
        url="https://example.invalid/staged-camoufox.zip",
        is_prerelease=version_data.get("prerelease", False),
        sha256=version_data.get("sha256"),
    )
    monkeypatch.setattr(
        pkgman, "list_available_versions", lambda *_args, **_kwargs: [staged_version]
    )
    monkeypatch.setattr(
        multiversion,
        "install_versioned",
        lambda *_args, **_kwargs: pytest.fail(
            "native bundle test must reuse the staged runtime"
        ),
    )

    original_launch_options = camoufox_sync_api.launch_options
    test_screen = Screen(max_width=1920, max_height=1080)

    def offline_launch_options(**kwargs):
        return original_launch_options(
            exclude_addons=list(DefaultAddons),
            screen=test_screen,
            **kwargs,
        )

    def reject_addon_download(*_args, **_kwargs) -> None:
        pytest.fail("native bundle test must not download Camoufox default addons")

    monkeypatch.setattr(
        camoufox_sync_api,
        "launch_options",
        offline_launch_options,
    )
    monkeypatch.setattr(
        camoufox_addons,
        "download_and_extract",
        reject_addon_download,
    )

    runtime_path = Path(pkgman.camoufox_path(download_if_missing=False))
    assert runtime_path.resolve() == expected_runtime_path
    executable_path = runtime_path / "Camoufox.app" / "Contents" / "MacOS" / "camoufox"
    properties_path = (
        runtime_path / "Camoufox.app" / "Contents" / "Resources" / "properties.json"
    )
    assert executable_path.is_file()
    assert properties_path.is_file()
    assert executable_path.parent.name == "MacOS"
    assert properties_path.parent.name == "Resources"

    browser_manager = CamoufoxBrowserManager(headless=True)
    browser_context = browser_manager.new_context()
    try:
        page = browser_context.new_page()
        assert page.url == "about:blank"
    finally:
        browser_context.close()
        browser_manager.close()

    persistent_manager = CamoufoxPersistentContextManager(
        user_data_dir=str(tmp_path / "camoufox-profile"),
        headless=True,
    )
    persistent_context = persistent_manager.new_context()
    try:
        page = persistent_context.new_page()
        assert page.url == "about:blank"
    finally:
        persistent_manager.close()

    # The offline wizard reuses this cache and verifies only about:blank, with
    # no launch-time update, addon/fingerprint download or provider state.
    from paper_fetch.offline_setup import Setup
    from paper_fetch.providers.browser_runtime import preparation

    monkeypatch.setattr(
        preparation,
        "prepare_camoufox_managed_runtime",
        lambda: pytest.fail("optional wizard must reuse the valid native bundle"),
    )
    setup = Setup(tmp_path, tmp_path / "offline.env")
    setup.browser(selected=True)
    assert "Camoufox local launch: ready" in setup.summary()
    assert "Publisher access: not tested" in setup.summary()
