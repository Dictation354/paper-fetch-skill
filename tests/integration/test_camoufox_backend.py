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
        pkgman.Version("beta.27", "152.0.3"), "https://example.test/old.zip", False
    )
    latest = pkgman.AvailableVersion(
        pkgman.Version("beta.28", "152.0.4"), "https://example.test/latest.zip", False
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
