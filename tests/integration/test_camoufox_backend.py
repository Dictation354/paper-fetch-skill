from __future__ import annotations
import json
from types import SimpleNamespace
from unittest import mock
import pytest
from paper_fetch.providers.browser_runtime import preparation


@pytest.fixture
def managed_camoufox(monkeypatch, tmp_path):
    """Exercise upstream version selection/install against an isolated fake archive."""
    import zipfile
    from camoufox import multiversion, pkgman

    root = tmp_path / "managed"
    root.mkdir()
    (root / "config.json").write_text(json.dumps({"channel": "official/stable"}))
    monkeypatch.setattr(pkgman, "INSTALL_DIR", root)
    monkeypatch.setattr(multiversion, "INSTALL_DIR", root)
    monkeypatch.setattr(multiversion, "BROWSERS_DIR", root / "browsers")
    monkeypatch.setattr(multiversion, "CONFIG_FILE", root / "config.json")
    monkeypatch.setattr(multiversion, "COMPAT_FLAG", root / ".0.5_FLAG")
    monkeypatch.setattr(pkgman, "OS_NAME", "lin")
    monkeypatch.setattr(multiversion, "OS_NAME", "lin")
    # File modes are immaterial to this dummy binary; avoid shelling out to chmod.
    monkeypatch.setattr(multiversion.os, "system", lambda _command: 0)

    old = pkgman.AvailableVersion(
        pkgman.Version("beta.30", "152.0.4"), "https://example.test/old.zip", False
    )
    latest = pkgman.AvailableVersion(
        pkgman.Version("beta.31", "152.0.4"), "https://example.test/latest.zip", False
    )
    query = mock.Mock(return_value=[latest, old])
    monkeypatch.setattr(pkgman, "list_available_versions", query)

    def download(file, _url):
        print("fake download progress")
        with zipfile.ZipFile(file, "w") as archive:
            archive.writestr("camoufox-bin", "dummy executable")
        file.seek(0)
        return file

    downloader = mock.Mock(side_effect=download)
    monkeypatch.setattr(pkgman.CamoufoxFetcher, "download_file", downloader)

    def install_local(version=old, *, active=True):
        path = root / "browsers" / "official" / version.version.full_string
        path.mkdir(parents=True, exist_ok=True)
        (path / "version.json").write_text(json.dumps(version.to_metadata()))
        (path / "camoufox-bin").write_text("old executable")
        if active:
            multiversion.set_active(path.relative_to(root).as_posix())
        return path

    return SimpleNamespace(
        root=root,
        pkgman=pkgman,
        multi=multiversion,
        old=old,
        latest=latest,
        query=query,
        download=downloader,
        install_local=install_local,
    )


def test_managed_camoufox_process_lock_prevents_duplicate_install(
    managed_camoufox, tmp_path
):
    import multiprocessing

    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("uses fork to inherit the isolated upstream download stub")
    env = managed_camoufox
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    downloads = tmp_path / "downloads"
    queries = tmp_path / "queries"
    original_download = env.download.side_effect

    def query(*_args, **_kwargs):
        with queries.open("a") as output:
            output.write("query\n")
        return [env.latest, env.old]

    env.query.side_effect = query

    def download(file, url):
        with downloads.open("a") as output:
            output.write("download\n")
        return original_download(file, url)

    env.download.side_effect = download

    def prepare():
        barrier.wait(timeout=10)
        assert preparation.prepare_camoufox_managed_runtime().valid

    processes = [context.Process(target=prepare) for _ in range(2)]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=15)
            assert process.exitcode == 0
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
    assert downloads.read_text() == "download\n"
    assert queries.read_text() == "query\n"
    assert preparation.probe_camoufox_managed_runtime().valid

    # A fresh interpreter has no inherited mocks or request-level preparation.
    import subprocess
    import sys
    import textwrap

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
            import sys
            from pathlib import Path
            from camoufox import pkgman, multiversion
            from paper_fetch.providers.browser_runtime import preparation

            root = Path(sys.argv[1])
            pkgman.INSTALL_DIR = multiversion.INSTALL_DIR = root
            multiversion.CONFIG_FILE = root / "config.json"
            multiversion.BROWSERS_DIR = root / "browsers"
            multiversion.COMPAT_FLAG = root / ".0.5_FLAG"
            pkgman.OS_NAME = multiversion.OS_NAME = "lin"

            def unexpected_query(*args, **kwargs):
                raise SystemExit("fresh process queried before 24 hours")

            pkgman.list_available_versions = unexpected_query
            assert preparation.prepare_camoufox_managed_runtime().valid
        """),
            str(env.root),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "Checking Camoufox" not in result.stderr


_PREPARE_FETCH_BROWSER = preparation.FetchBrowserPreparation.prepare


@pytest.mark.parametrize("first", ["fetch", "auth", "preflight", "project"])
def test_automatic_preparation_entrypoints_share_update_interval(
    managed_camoufox, monkeypatch, tmp_path, first
):
    import camoufox.sync_api as camoufox_sync
    import playwright.sync_api as playwright_sync
    from paper_fetch import auth, browser_preflight
    from paper_fetch.providers.base import ProviderFailure
    from paper_fetch.providers.browser_runtime.camoufox_manager import (
        _launch_executable_path,
    )

    env = managed_camoufox
    monkeypatch.setattr(
        preparation.FetchBrowserPreparation, "prepare", _PREPARE_FETCH_BROWSER
    )
    monkeypatch.setattr(preparation, "find_spec", lambda _name: object())
    playwright = SimpleNamespace(stop=mock.Mock())
    monkeypatch.setattr(
        playwright_sync,
        "sync_playwright",
        lambda: SimpleNamespace(start=lambda: playwright),
    )
    launch = mock.Mock(side_effect=RuntimeError("launch boundary reached"))
    monkeypatch.setattr(camoufox_sync, "NewBrowser", launch)
    runtime_env = {"XDG_DATA_HOME": str(tmp_path / "data")}

    def prepare(route):
        if route == "project":
            assert preparation.prepare_camoufox_managed_runtime().valid
        elif route == "fetch":
            request = preparation.FetchBrowserPreparation()
            token = preparation.fetch_browser_preparation.set(request)
            try:
                request.prepare(runtime_env, lambda: None)
                request.require()
                assert _launch_executable_path(None) is None
            finally:
                preparation.fetch_browser_preparation.reset(token)
        elif route == "auth":
            with pytest.raises(ProviderFailure, match="launch boundary reached"):
                auth.authenticate_provider_profile(
                    provider="wiley", env=runtime_env, confirm=None
                )
        else:
            result = browser_preflight.preflight_browser_provider(
                "ieee", env=runtime_env, save_storage_state=False
            )
            assert result.status == "runtime_error"
            assert "launch boundary reached" in result.message

    prepare(first)
    record = (env.root / preparation.UPDATE_CHECK_FILENAME).read_bytes()
    for route in ("fetch", "auth", "preflight", "project"):
        prepare(route)
        assert (env.root / preparation.UPDATE_CHECK_FILENAME).read_bytes() == record
    env.query.assert_called_once()
    env.download.assert_called_once()


@pytest.mark.parametrize("pinned", [False, True])
def test_managed_camoufox_rejects_runtime_below_playwright_floor(
    managed_camoufox, pinned
):
    """An existing executable cannot bypass the installed driver's protocol floor."""
    env = managed_camoufox
    incompatible = env.pkgman.AvailableVersion(
        env.pkgman.Version("beta.29", "152.0.4"),
        "https://example.test/incompatible.zip",
        False,
    )
    assert not incompatible.version.is_supported()
    path = env.install_local(incompatible)
    config = env.multi.load_config()
    if pinned:
        config["pinned"] = incompatible.version.full_string
        env.multi.save_config(config)
    env.query.return_value = [env.latest, incompatible]
    if not pinned:
        env.query.side_effect = OSError("offline")

    probe = preparation.probe_camoufox_managed_runtime()
    assert probe.state == "incompatible" and not probe.valid
    with pytest.raises(RuntimeError, match="Camoufox browser preparation failed"):
        preparation.prepare_camoufox_managed_runtime()

    env.download.assert_not_called()
    assert env.multi.load_config() == config
    assert (path / "camoufox-bin").read_text() == "old executable"


@pytest.mark.parametrize("local", [False, True])
def test_managed_camoufox_default_agrees_with_upstream_path_resolution(
    managed_camoufox, local
):
    env = managed_camoufox
    env.install_local()
    if local:
        env.latest.is_prerelease = True
        env.install_local(env.latest, active=False)
    env.latest.is_prerelease = True
    config = env.multi.load_config()
    config.pop("channel")
    env.multi.save_config(config)
    before = env.multi.CONFIG_FILE.read_bytes()

    assert preparation.probe_camoufox_managed_runtime().valid
    assert env.multi.CONFIG_FILE.read_bytes() == before
    result = preparation.prepare_camoufox_managed_runtime()

    assert result.valid and result.version == env.latest.version.full_string
    assert env.multi.load_config()["channel"] == "official/prerelease"
    assert env.pkgman.camoufox_path(download_if_missing=False) == result.runtime_path
    assert env.multi.get_active_path() == result.runtime_path
    assert env.download.call_count == int(not local)
