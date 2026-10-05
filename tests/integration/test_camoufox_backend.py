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

    monkeypatch.setattr(preparation, "_browser_pin", lambda _config: None)
    root = tmp_path / "managed"
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
    original_download = env.download.side_effect

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
    assert preparation.probe_camoufox_managed_runtime().valid


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
def test_managed_camoufox_pairing_agrees_with_upstream_path_resolution(
    managed_camoufox, monkeypatch, local
):
    browser_pin = pytest.importorskip("camoufox.browser_pin")
    env = managed_camoufox
    pin = browser_pin.BrowserPin(
        tag="v152.0.4-beta.31",
        repo="daijro/camoufox",
        repo_name="official",
        version="152.0.4",
        build="beta.31",
    )
    monkeypatch.setattr(browser_pin, "load_pin", lambda: pin)
    monkeypatch.setattr(preparation, "_browser_pin", browser_pin.effective_pin)
    env.install_local()
    if local:
        env.install_local(env.latest, active=False)
    before = env.multi.CONFIG_FILE.read_bytes()

    probe = preparation.probe_camoufox_managed_runtime()
    assert probe.valid is local
    assert env.multi.CONFIG_FILE.read_bytes() == before
    result = preparation.prepare_camoufox_managed_runtime()

    assert result.valid and result.version == pin.spec
    assert env.pkgman.camoufox_path(download_if_missing=False) == result.runtime_path
    assert env.multi.get_active_path() == result.runtime_path
    assert env.download.call_count == int(not local)
