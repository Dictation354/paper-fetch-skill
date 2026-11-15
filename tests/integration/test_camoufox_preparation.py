"""Camoufox package preparation contracts run where that engine is installed."""

from __future__ import annotations
import json
from types import SimpleNamespace
import threading
from unittest import mock
import pytest
from paper_fetch.config import (
    XDG_DATA_HOME_ENV_VAR,
)
from paper_fetch.providers import _playwright_browser, browser_runtime
from paper_fetch.providers.base import ProviderFailure
from paper_fetch.providers.browser_runtime.backends.camoufox import (
    CamoufoxBackend,
    _dependency_details,
)
from paper_fetch.providers.browser_runtime.camoufox_manager import (
    _launch_executable_path,
)
from paper_fetch.providers.browser_runtime import preparation
from paper_fetch.providers.browser_runtime import context as browser_runtime_context
from paper_fetch.providers.browser_runtime.types import (
    BrowserRuntimeConfig,
)


pytest.importorskip("camoufox")


@pytest.fixture
def fingerprint_model(monkeypatch, tmp_path):
    import hashlib
    from io import BytesIO
    from zipfile import ZipFile
    import requests
    from camoufox import fpgen_model, pkgman

    members = {"values.json.zst": b"model", "values.dat.zst": b"data"}
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    payload = buffer.getvalue()
    pin = {
        "repo": "scrapfly/fingerprint-generator",
        "tag": "model-2/2026",
        "asset": "model-release.zip",
        "url": "https://github.com/scrapfly/fingerprint-generator/releases/download/model-2/2026/model-release.zip",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "file_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in members.items()
        },
        "decompressed_sha256": {},
    }
    data_dir = tmp_path / "model"
    monkeypatch.delenv(fpgen_model.CUSTOM_MODEL_ENV, raising=False)
    monkeypatch.setattr(fpgen_model, "PIN", pin)
    monkeypatch.setattr(fpgen_model, "fpgen_data_dir", lambda: data_dir)
    direct = mock.Mock(side_effect=requests.HTTPError("504 Gateway Time-out"))
    monkeypatch.setattr(fpgen_model, "webdl", direct)
    release = mock.Mock(return_value={"assets": [{"name": pin["asset"], "id": 123}]})
    monkeypatch.setattr(pkgman, "github_api", release)
    monkeypatch.setattr(pkgman, "GITHUB_TOKEN", "test-token")
    response = mock.MagicMock(content=payload)
    response.__enter__.return_value = response
    download = mock.Mock(return_value=response)
    monkeypatch.setattr(requests, "get", download)
    return SimpleNamespace(
        model=fpgen_model,
        data_dir=data_dir,
        pin=pin,
        payload=payload,
        members=members,
        direct=direct,
        release=release,
        download=download,
        response=response,
    )


def test_model_download_falls_back_to_pinned_github_asset(fingerprint_model, capsys):
    env = fingerprint_model
    preparation.prepare_camoufox_fingerprint_model()
    assert env.model.is_pinned()
    assert (env.data_dir / env.model.STAMP).read_text().strip() == env.pin["sha256"]
    for name, content in env.members.items():
        assert (env.data_dir / name).read_bytes() == content
        assert int((env.data_dir / name).stat().st_mtime) == env.model.PINNED_MTIME
    env.release.assert_called_once_with(
        "repos/scrapfly/fingerprint-generator/releases/tags/model-2%2F2026"
    )
    env.download.assert_called_once_with(
        "https://api.github.com/repos/scrapfly/fingerprint-generator/releases/assets/123",
        headers={
            "Accept": "application/octet-stream",
            "Authorization": "Bearer test-token",
        },
        timeout=60,
    )
    preparation.prepare_camoufox_fingerprint_model()
    assert env.direct.call_count == env.download.call_count == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "via GitHub API" in captured.err


@pytest.mark.parametrize("failure", ["archive_hash", "members", "member_hash"])
def test_model_api_fallback_keeps_all_hash_checks(fingerprint_model, failure):
    import hashlib

    env = fingerprint_model
    if failure == "archive_hash":
        env.response.content = b"corrupted download"
    elif failure == "members":
        env.pin["file_sha256"]["unexpected.zst"] = "0" * 64
    else:
        env.pin["file_sha256"]["values.dat.zst"] = hashlib.sha256(b"other").hexdigest()
    with pytest.raises(env.model.CorruptedDownload):
        preparation.prepare_camoufox_fingerprint_model()
    assert not env.data_dir.exists()


@pytest.mark.parametrize("source", ["cache", "direct", "custom"])
def test_model_does_not_use_api_when_not_needed(fingerprint_model, monkeypatch, source):
    from io import BytesIO

    env = fingerprint_model
    env.direct.side_effect = None
    env.direct.return_value = BytesIO(env.payload)
    if source == "cache":
        env.model.ensure_fpgen_model()
        env.direct.reset_mock()
    elif source == "custom":
        monkeypatch.setenv(env.model.CUSTOM_MODEL_ENV, "https://example.test/model.zip")
    preparation.prepare_camoufox_fingerprint_model()
    assert env.direct.call_count == int(source == "direct")
    env.release.assert_not_called()
    env.download.assert_not_called()


@pytest.mark.parametrize(
    "error", [PermissionError("read-only"), ValueError("invalid model")]
)
def test_model_non_network_failure_does_not_trigger_api(fingerprint_model, error):
    env = fingerprint_model
    env.direct.side_effect = error
    expected = (
        env.model.FpgenModelError if isinstance(error, PermissionError) else type(error)
    )
    with pytest.raises(expected):
        preparation.prepare_camoufox_fingerprint_model()
    env.release.assert_not_called()
    env.download.assert_not_called()


def test_original_model_hash_failure_does_not_trigger_api(fingerprint_model):
    from io import BytesIO

    env = fingerprint_model
    env.direct.side_effect = None
    env.direct.return_value = BytesIO(b"corrupted download")
    with pytest.raises(env.model.CorruptedDownload):
        preparation.prepare_camoufox_fingerprint_model()
    env.release.assert_not_called()
    env.download.assert_not_called()


def test_model_api_download_failure_propagates(fingerprint_model):
    import requests

    env = fingerprint_model
    env.response.raise_for_status.side_effect = requests.HTTPError(
        "API download failed"
    )
    with pytest.raises(requests.HTTPError, match="API download failed"):
        preparation.prepare_camoufox_fingerprint_model()
    assert not env.data_dir.exists()


def test_model_api_missing_asset_does_not_download(fingerprint_model):
    env = fingerprint_model
    env.release.return_value = {"assets": [{"name": "other.zip", "id": 456}]}
    with pytest.raises(RuntimeError, match="Pinned fpgen model asset is missing"):
        preparation.prepare_camoufox_fingerprint_model()
    env.download.assert_not_called()


@pytest.fixture
def managed_camoufox(monkeypatch, tmp_path):
    """Exercise upstream version selection/install against an isolated fake archive."""
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox._dependency_details",
        _dependency_details,
    )
    monkeypatch.setattr(preparation, "prepare_camoufox_fingerprint_model", lambda: None)
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
            archive.writestr(zipfile.ZipInfo("camoufox-bin"), "dummy executable")
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

    clock = [1_000_000.0]
    monkeypatch.setattr(preparation, "time", SimpleNamespace(time=lambda: clock[0]))
    return SimpleNamespace(
        clock=clock,
        check_path=root / preparation.UPDATE_CHECK_FILENAME,
        root=root,
        pkgman=pkgman,
        multi=multiversion,
        old=old,
        latest=latest,
        query=query,
        download=downloader,
        install_local=install_local,
    )


def test_managed_camoufox_missing_installs_and_latest_reuses(managed_camoufox, capsys):
    env = managed_camoufox
    first = preparation.prepare_camoufox_managed_runtime()
    assert first.valid and first.version == env.latest.version.full_string
    assert preparation.prepare_camoufox_managed_runtime() == first
    assert env.query.call_count == 1
    env.download.assert_called_once()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "fake download progress" in captured.err
    assert env.multi.COMPAT_FLAG.is_file()


@pytest.mark.parametrize("old_active", [False, True])
def test_managed_camoufox_defaults_to_prerelease_and_migrates_active(
    managed_camoufox, old_active
):
    env = managed_camoufox
    if old_active:
        env.install_local()
    config = env.multi.load_config()
    config.pop("channel")
    config["unrelated"] = "preserve"
    env.multi.save_config(config)
    env.latest.is_prerelease = True
    before = env.multi.CONFIG_FILE.read_bytes()
    probe = preparation.probe_camoufox_managed_runtime()
    assert probe.valid is old_active
    assert env.multi.CONFIG_FILE.read_bytes() == before
    env.query.assert_not_called()

    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid and result.version == env.latest.version.full_string
    assert env.multi.load_config()["channel"] == "official/prerelease"
    assert env.multi.load_config()["unrelated"] == "preserve"
    assert env.query.call_args.kwargs == {"include_prerelease": True}
    assert env.pkgman.camoufox_path(download_if_missing=False) == result.runtime_path
    assert preparation.prepare_camoufox_managed_runtime() == result
    assert env.query.call_count == 1
    env.download.assert_called_once()


def test_managed_camoufox_new_prerelease_updates_after_interval(managed_camoufox):
    env = managed_camoufox
    env.multi.CONFIG_FILE.unlink()
    env.old.is_prerelease = env.latest.is_prerelease = True
    env.query.return_value = [env.old]
    first = preparation.prepare_camoufox_managed_runtime()
    env.query.return_value = [env.latest, env.old]
    assert preparation.prepare_camoufox_managed_runtime() == first
    env.clock[0] += 86400
    second = preparation.prepare_camoufox_managed_runtime()
    assert first.version == env.old.version.full_string
    assert second.version == env.latest.version.full_string
    assert first.runtime_path.is_dir()
    assert env.multi.load_config()["active_version"] == second.active_spec
    assert env.download.call_count == 2


def test_managed_camoufox_interval_runs_from_completion_without_sliding(
    managed_camoufox, capsys
):
    env = managed_camoufox

    def query(*_args, **_kwargs):
        env.clock[0] += 90
        return [env.latest]

    env.query.side_effect = query
    first = preparation.prepare_camoufox_managed_runtime()
    record = env.check_path.read_bytes()
    assert json.loads(record)["checked_at"] == env.clock[0]
    assert json.loads(record)[
        "python_package_version"
    ] == preparation.distribution_version("camoufox")
    capsys.readouterr()
    env.multi.COMPAT_FLAG.unlink()
    for elapsed in (1, 43200, 86399):
        env.clock[0] = json.loads(record)["checked_at"] + elapsed
        assert preparation.prepare_camoufox_managed_runtime() == first
        assert env.check_path.read_bytes() == record
    assert capsys.readouterr().err == ""
    assert env.multi.COMPAT_FLAG.exists()
    env.query.assert_called_once()
    env.clock[0] += 1
    assert preparation.prepare_camoufox_managed_runtime() == first
    assert env.query.call_count == 2
    assert json.loads(env.check_path.read_text())["checked_at"] == env.clock[0]


@pytest.mark.parametrize("failure", ["query", "download"])
def test_managed_camoufox_failed_update_allows_immediate_retry(
    managed_camoufox, failure
):
    env = managed_camoufox
    env.install_local()
    failed = env.query if failure == "query" else env.download

    def fail(*_args, **_kwargs):
        env.clock[0] += 60
        raise OSError("offline")

    failed.side_effect = fail
    result = preparation.prepare_camoufox_managed_runtime()
    completed = env.clock[0]
    assert json.loads(env.check_path.read_text())["result"] == "failed"
    assert json.loads(env.check_path.read_text())["checked_at"] is None
    env.clock[0] += 1
    assert preparation.prepare_camoufox_managed_runtime() == result
    assert failed.call_count == 2
    env.clock[0] = completed + 86400
    assert preparation.prepare_camoufox_managed_runtime() == result
    assert failed.call_count == 3


@pytest.mark.parametrize(
    "broken", ["missing", "executable", "metadata", "incompatible"]
)
def test_managed_camoufox_invalid_runtime_bypasses_interval(managed_camoufox, broken):
    env = managed_camoufox
    first = preparation.prepare_camoufox_managed_runtime()
    if broken == "missing":
        import shutil

        shutil.rmtree(first.runtime_path)
    elif broken == "executable":
        first.executable_path.unlink()
    elif broken == "metadata":
        (first.runtime_path / "version.json").write_text("{")
    else:
        (first.runtime_path / "version.json").write_text(
            json.dumps(
                env.pkgman.AvailableVersion(
                    env.pkgman.Version("beta.29", "152.0.4"),
                    "https://example.test/old.zip",
                    False,
                ).to_metadata()
            )
        )
    assert preparation.prepare_camoufox_managed_runtime().valid
    assert env.query.call_count == 2
    assert env.download.call_count == 2


@pytest.mark.parametrize("changed", ["channel", "pinned", "pinned_sha", "package"])
def test_managed_camoufox_configuration_change_bypasses_interval(
    managed_camoufox, monkeypatch, changed
):
    env = managed_camoufox
    env.query.return_value = [env.old]
    preparation.prepare_camoufox_managed_runtime()
    config = env.multi.load_config()
    if changed == "package":
        monkeypatch.setattr(
            preparation, "distribution_version", lambda _name: "new-package"
        )
    else:
        config[changed] = {
            "channel": "official/prerelease",
            "pinned": env.latest.version.full_string,
            "pinned_sha": "new-sha",
        }[changed]
        env.multi.save_config(config)
    env.query.return_value = [env.latest]
    env.latest.is_prerelease = changed == "channel"
    assert preparation.prepare_camoufox_managed_runtime().valid
    assert env.query.call_count == 2
    record = json.loads(env.check_path.read_text())
    if changed == "package":
        assert record["python_package_version"] == "new-package"
    else:
        assert record[changed] == config[changed]


def test_managed_camoufox_changed_pin_reuses_local_without_refreshing_record(
    managed_camoufox, monkeypatch
):
    env = managed_camoufox
    env.install_local()
    preparation.prepare_camoufox_managed_runtime()
    record = env.check_path.read_bytes()
    config = env.multi.load_config()
    config["pinned"] = env.old.version.full_string
    env.multi.save_config(config)
    monkeypatch.setattr(
        preparation, "distribution_version", lambda _name: "new-package"
    )
    env.clock[0] += 86400
    assert (
        preparation.prepare_camoufox_managed_runtime().version
        == env.old.version.full_string
    )
    assert env.check_path.read_bytes() == record
    env.query.assert_called_once()


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "{",
        "[]",
        "{}",
        '{"checked_at": 1}',
        "future",
        "string",
        "null",
        "bool",
        "nan",
        "infinity",
        "negative",
        "huge",
        "missing-key",
    ],
)
def test_managed_camoufox_invalid_check_record_triggers_query(
    managed_camoufox, payload
):
    env = managed_camoufox
    preparation.prepare_camoufox_managed_runtime()
    record = json.loads(env.check_path.read_text())
    timestamps = {
        "future": env.clock[0] + 1,
        "string": str(env.clock[0]),
        "null": None,
        "bool": True,
        "nan": float("nan"),
        "infinity": float("inf"),
        "negative": -1,
        "huge": 10**400,
    }
    if payload is None:
        env.check_path.unlink()
    elif payload in timestamps:
        record["checked_at"] = timestamps[payload]
        env.check_path.write_text(json.dumps(record))
    elif payload == "missing-key":
        record.pop("pinned")
        env.check_path.write_text(json.dumps(record))
    else:
        env.check_path.write_text(payload)
    assert preparation.prepare_camoufox_managed_runtime().valid
    assert env.query.call_count == 2


def test_managed_camoufox_check_record_write_failure_preserves_result(
    managed_camoufox, monkeypatch, capsys
):
    env = managed_camoufox
    monkeypatch.setattr(
        preparation, "_atomic_write_json", mock.Mock(side_effect=OSError("read-only"))
    )
    assert preparation.prepare_camoufox_managed_runtime().valid
    assert "Could not save Camoufox update check: read-only" in capsys.readouterr().err
    assert not env.check_path.exists()


@pytest.mark.parametrize("prerelease", [False, True])
def test_managed_camoufox_prerelease_filters_incompatible(managed_camoufox, prerelease):
    env = managed_camoufox
    env.multi.CONFIG_FILE.unlink()
    env.old.is_prerelease = True
    unsupported = env.pkgman.AvailableVersion(
        env.pkgman.Version("2.0.0", "152.0.4"),
        "https://example.test/unsupported.zip",
        prerelease,
    )
    env.query.return_value = [unsupported, env.old]
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.version == env.old.version.full_string
    assert env.query.call_args.kwargs == {"include_prerelease": True}


@pytest.mark.parametrize("failure", ["query", "download"])
def test_managed_camoufox_default_migration_falls_back_locally(
    managed_camoufox, failure
):
    env = managed_camoufox
    old_path = env.install_local()
    config = env.multi.load_config()
    config.pop("channel")
    env.multi.save_config(config)
    env.latest.is_prerelease = True
    (env.query if failure == "query" else env.download).side_effect = OSError("offline")
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.runtime_path == old_path
    assert env.multi.load_config()["channel"] == "official/prerelease"
    assert env.pkgman.camoufox_path(download_if_missing=False) == old_path


def test_managed_camoufox_updates_without_removing_old(managed_camoufox):
    env = managed_camoufox
    old_path = env.install_local()
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.version == env.latest.version.full_string
    assert (old_path / "camoufox-bin").read_text() == "old executable"
    assert env.multi.load_config()["active_version"] == result.active_spec


@pytest.mark.parametrize("local", [True, False])
@pytest.mark.parametrize("channel", ["stable", "prerelease"])
def test_managed_camoufox_pin_only_prepares_requested_version(
    managed_camoufox, local, channel
):
    env = managed_camoufox
    if local:
        env.install_local()
    env.multi.save_config(
        {
            "channel": f"official/{channel}",
            "pinned": env.old.version.full_string,
            "unrelated": "preserve",
        }
    )
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.version == env.old.version.full_string
    assert env.multi.load_config()["pinned"] == env.old.version.full_string
    assert env.multi.load_config()["unrelated"] == "preserve"
    assert env.query.call_count == (0 if local else 1)
    assert env.download.call_count == (0 if local else 1)


@pytest.mark.parametrize("latest_prerelease", [False, True])
def test_managed_camoufox_prerelease_selects_latest_compatible(
    managed_camoufox, latest_prerelease
):
    env = managed_camoufox
    env.latest.is_prerelease = latest_prerelease
    env.old.is_prerelease = not latest_prerelease
    env.multi.save_config({"channel": "official/prerelease"})
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.version == env.latest.version.full_string
    assert env.query.call_args.kwargs == {"include_prerelease": True}
    assert env.query.call_args.args[0].name == "Official"
    assert env.multi.load_config()["channel"] == "official/prerelease"


def test_managed_camoufox_stable_excludes_prerelease(managed_camoufox):
    env = managed_camoufox
    env.latest.is_prerelease = True
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.version == env.old.version.full_string
    assert env.query.call_args.kwargs == {"include_prerelease": False}


@pytest.mark.parametrize("failure", ["query", "download", "validation"])
@pytest.mark.parametrize("local", [True, False])
def test_managed_camoufox_failure_uses_only_valid_local_runtime(
    managed_camoufox, capsys, failure, local
):
    env = managed_camoufox
    if local:
        env.install_local()
    if failure == "query":
        env.query.side_effect = OSError("offline")
    elif failure == "download":
        env.download.side_effect = OSError("interrupted")
    else:
        # A successfully unpacked archive can still lack its executable.
        import zipfile

        def empty_archive(file, _url):
            with zipfile.ZipFile(file, "w"):
                pass
            file.seek(0)

        env.download.side_effect = empty_archive
    if local:
        result = preparation.prepare_camoufox_managed_runtime()
        assert result.valid and result.version == env.old.version.full_string
        assert preparation.probe_camoufox_managed_runtime() == result
        assert "using local" in capsys.readouterr().err
    else:
        with pytest.raises(RuntimeError, match="Camoufox browser preparation failed"):
            preparation.prepare_camoufox_managed_runtime()
        assert not preparation.probe_camoufox_managed_runtime().valid
        assert json.loads(env.check_path.read_text())["result"] == "failed"
        # An unsuccessful check cannot delay preparation without a valid browser.
        with pytest.raises(RuntimeError, match="Camoufox browser preparation failed"):
            preparation.prepare_camoufox_managed_runtime()
        assert env.query.call_count == 2


def test_managed_camoufox_repairs_only_broken_target(managed_camoufox):
    env = managed_camoufox
    old_path = env.install_local()
    target = env.install_local(env.latest, active=False)
    (target / "camoufox-bin").unlink()
    (target / "leftover").touch()
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid and result.runtime_path == target
    assert not (target / "leftover").exists()
    assert old_path.is_dir()
    env.download.assert_called_once()


@pytest.mark.parametrize(
    "payload", ["{", "[]", '{"active_version": 42}', '{"channel":"official/unknown"}']
)
def test_managed_camoufox_rejects_config_without_reset(managed_camoufox, payload):
    env = managed_camoufox
    env.root.mkdir(exist_ok=True)
    env.multi.CONFIG_FILE.write_text(payload)
    with pytest.raises(RuntimeError, match="preparation failed"):
        preparation.prepare_camoufox_managed_runtime()
    assert env.multi.CONFIG_FILE.read_text() == payload
    env.query.assert_not_called()
    env.download.assert_not_called()


@pytest.mark.parametrize(
    "unsafe",
    ["active", "target", "config", "lock", "flag", "check", "metadata", "executable"],
)
def test_managed_camoufox_rejects_unsafe_paths(managed_camoufox, tmp_path, unsafe):
    env = managed_camoufox
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep"
    marker.write_text("untouched")
    env.root.mkdir(exist_ok=True)
    if unsafe == "active":
        env.multi.save_config({"active_version": "../outside"})
    else:
        target = env.install_local(env.latest, active=False)
        paths = {
            "target": target,
            "config": env.multi.CONFIG_FILE,
            "lock": env.root / ".paper-fetch-prepare.lock",
            "flag": env.multi.COMPAT_FLAG,
            "check": env.check_path,
            "metadata": target / "version.json",
            "executable": target / "camoufox-bin",
        }
        path = paths[unsafe]
        if path.is_dir():
            import shutil

            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        try:
            path.symlink_to(
                outside if unsafe == "target" else marker,
                target_is_directory=unsafe == "target",
            )
        except OSError:
            pytest.skip("symlink creation unavailable")
    with pytest.raises(RuntimeError, match="preparation failed"):
        preparation.prepare_camoufox_managed_runtime()
    assert marker.read_text() == "untouched"
    env.download.assert_not_called()


def test_managed_camoufox_concurrent_preparation_installs_once(managed_camoufox):
    from concurrent.futures import ThreadPoolExecutor

    env = managed_camoufox
    barrier = threading.Barrier(2)

    def prepare():
        barrier.wait(timeout=5)
        return preparation.prepare_camoufox_managed_runtime()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: prepare(), range(2)))
    assert results[0] == results[1]
    assert all(result.valid for result in results)
    env.download.assert_called_once()
    env.query.assert_called_once()


def test_managed_camoufox_static_status_never_prepares(managed_camoufox):
    env = managed_camoufox
    before = env.multi.CONFIG_FILE.read_bytes()
    status = CamoufoxBackend().probe_runtime_status({}, provider="science")
    assert status.status == "not_configured"
    assert env.multi.CONFIG_FILE.read_bytes() == before
    assert not env.multi.COMPAT_FLAG.exists()
    env.query.assert_not_called()
    env.download.assert_not_called()


def test_explicit_camoufox_binary_skips_management(monkeypatch):
    prepare = mock.Mock(side_effect=AssertionError("must not manage explicit binary"))
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.camoufox_manager.prepare_camoufox_managed_runtime",
        prepare,
    )
    assert _launch_executable_path("/custom/camoufox") == "/custom/camoufox"
    prepare.assert_not_called()


@pytest.mark.parametrize("route", ["fetch", "preflight", "auth"])
@pytest.mark.parametrize("download_available", [True, False])
def test_browser_entrypoints_prepare_missing_runtime(
    managed_camoufox, monkeypatch, tmp_path, route, download_available
):
    from paper_fetch import auth, browser_preflight
    from paper_fetch.providers.browser_runtime import byparr_engine, byparr_manager
    from paper_fetch.providers.browser_runtime.backends import byparr

    env = managed_camoufox
    monkeypatch.setattr(byparr_engine, "engine_name", lambda: "camoufox")
    if not download_available:
        env.query.side_effect = OSError("offline")
    monkeypatch.setattr(
        byparr,
        "_dependency_details",
        lambda: {
            "runtime_valid": True,
            "packages": {"camoufox": True, "playwright": True},
        },
    )
    # Observe preparation at the manager's component boundary; no process runs.
    launch = mock.Mock(side_effect=RuntimeError("launch boundary reached"))
    monkeypatch.setattr(byparr_manager, "prepare_components", launch)
    monkeypatch.setattr(
        _playwright_browser,
        "open_browser_context",
        browser_runtime_context.open_browser_context,
    )
    runtime_env = {XDG_DATA_HOME_ENV_VAR: str(tmp_path / "data")}
    expected = (
        "launch boundary reached"
        if download_available
        else "Camoufox browser preparation failed"
    )
    if route == "fetch":
        config = CamoufoxBackend().load_runtime_config(
            runtime_env, provider="ieee", doi="10.1109/example"
        )
        byparr.DEFAULT_BYPARR_BACKEND.ensure_runtime_ready(config)
        with pytest.raises(browser_runtime.BrowserRuntimeFailure, match=expected):
            browser_runtime.fetch_html_with_browser(
                ["https://ieeexplore.ieee.org/document/123"],
                publisher="ieee",
                config=config,
            )
    elif route == "preflight":
        result = browser_preflight.preflight_browser_provider(
            "ieee",
            env=runtime_env,
        )
        assert result.status == "runtime_error"
        assert expected in result.message
    else:
        with pytest.raises(ProviderFailure, match=expected):
            auth.authenticate_provider_profile(
                provider="wiley", env=runtime_env, confirm=None
            )
    assert preparation.probe_camoufox_managed_runtime().valid is download_available
    assert launch.call_count == int(download_available)
    env.query.assert_called_once()


def test_camoufox_missing_python_dependency_still_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "paper_fetch.providers.browser_runtime.backends.camoufox._dependency_details",
        lambda: {
            "runtime_valid": False,
            "packages": {"camoufox": False, "playwright": True},
        },
    )
    config = BrowserRuntimeConfig(
        provider="science",
        doi="10.1126/example",
        artifact_dir=tmp_path,
        headless=True,
        user_agent=None,
    )
    with pytest.raises(ProviderFailure, match="requires compatible") as error:
        CamoufoxBackend().ensure_runtime_ready(config)
    assert error.value.code == "not_configured"


def test_managed_camoufox_pin_sha_does_not_reuse_different_asset(managed_camoufox):
    import hashlib
    import io

    env = managed_camoufox
    old_path = env.install_local()
    env.query.return_value = [env.old]
    preparation.prepare_camoufox_managed_runtime()
    env.query.reset_mock()
    archive = env.download.side_effect(io.BytesIO(), "https://example.test/old.zip")
    env.old.sha256 = hashlib.sha256(archive.getvalue()).hexdigest()
    env.multi.save_config(
        {
            "active_version": old_path.relative_to(env.root).as_posix(),
            "channel": "official/stable",
            "pinned": env.old.version.full_string,
            "pinned_sha": env.old.sha256,
        }
    )
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid and result.runtime_path.name.endswith(f"-{env.old.sha256[:8]}")
    assert env.multi.load_config()["pinned_sha"] == env.old.sha256
    env.download.assert_called_once()
    env.query.assert_called_once()
    assert old_path.is_dir()


def test_managed_camoufox_repairs_pinned_corrupt_metadata(managed_camoufox):
    env = managed_camoufox
    target = env.install_local()
    (target / "version.json").write_text("{}")
    config = env.multi.load_config()
    config.update(channel="official/stable", pinned=env.old.version.full_string)
    env.multi.save_config(config)
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid and result.runtime_path == target
    env.download.assert_called_once()


def test_managed_camoufox_mismatched_target_metadata_is_repaired(managed_camoufox):
    env = managed_camoufox
    env.install_local()
    target = env.install_local(env.latest, active=False)
    (target / "version.json").write_text(json.dumps(env.old.to_metadata()))
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid and result.version == env.latest.version.full_string
    env.download.assert_called_once()


def test_managed_camoufox_update_failure_keeps_legacy_cache(managed_camoufox):
    env = managed_camoufox
    env.root.mkdir(exist_ok=True)
    (env.root / "version.json").write_text(json.dumps(env.old.to_metadata()))
    (env.root / "camoufox-bin").write_text("legacy binary")
    env.query.side_effect = OSError("offline")
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid and result.runtime_path == env.root
    # Upstream resolution would erase this legacy cache without the compatibility flag.
    assert env.pkgman.camoufox_path(download_if_missing=False) == env.root
    assert (env.root / "camoufox-bin").read_text() == "legacy binary"


def test_managed_camoufox_macos_bundle_probe_preserves_layout(
    managed_camoufox, monkeypatch
):
    env = managed_camoufox
    path = env.install_local(env.latest)
    config = env.multi.load_config()
    config["channel"] = "official/stable"
    env.multi.save_config(config)
    (path / "camoufox-bin").unlink()
    contents = path / "Camoufox.app" / "Contents"
    (contents / "Resources").mkdir(parents=True)
    (contents / "Resources" / "properties.json").write_text("{}")
    (contents / "MacOS").mkdir()
    (contents / "MacOS" / "camoufox").write_text("dummy mac binary")
    monkeypatch.setattr(env.pkgman, "OS_NAME", "mac")
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid
    assert result.executable_path == contents / "MacOS" / "camoufox"
    assert env.pkgman.camoufox_path(download_if_missing=False) == path
    env.download.assert_not_called()


def test_managed_camoufox_pin_failure_does_not_launch_wrong_version(managed_camoufox):
    env = managed_camoufox
    env.install_local()
    config = env.multi.load_config()
    config.update(channel="official/stable", pinned=env.latest.version.full_string)
    env.multi.save_config(config)
    env.query.side_effect = OSError("offline")
    with pytest.raises(RuntimeError, match="preparation failed"):
        preparation.prepare_camoufox_managed_runtime()
    assert env.multi.load_config() == config
    assert (
        preparation.probe_camoufox_managed_runtime().version
        == env.old.version.full_string
    )


def test_managed_camoufox_never_deletes_valid_active_for_mismatched_catalog(
    managed_camoufox,
):
    env = managed_camoufox
    target = env.install_local(env.latest)
    (target / "version.json").write_text(json.dumps(env.old.to_metadata()))
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid and result.version == env.old.version.full_string
    assert (target / "camoufox-bin").read_text() == "old executable"
    env.download.assert_not_called()


def test_managed_camoufox_pin_without_channel_is_preserved(managed_camoufox):
    env = managed_camoufox
    env.install_local()
    config = env.multi.load_config()
    config.pop("channel")
    config["pinned"] = env.old.version.full_string
    env.multi.save_config(config)
    result = preparation.prepare_camoufox_managed_runtime()
    assert result.valid and result.version == env.old.version.full_string
    assert env.multi.load_config() == config
    env.query.assert_not_called()
    env.download.assert_not_called()


@pytest.mark.parametrize("stage", ["query", "download"])
def test_managed_camoufox_cancellation_does_not_fall_back(managed_camoufox, stage):
    from paper_fetch.http import RequestCancelledError

    env = managed_camoufox
    path = env.install_local()
    (
        env.query if stage == "query" else env.download
    ).side_effect = RequestCancelledError("cancelled")
    with pytest.raises(RequestCancelledError):
        preparation.prepare_camoufox_managed_runtime()
    assert preparation.probe_camoufox_managed_runtime().runtime_path == path
    assert json.loads(env.check_path.read_text())["result"] == "cancelled"


@pytest.mark.parametrize("stage", ["query", "download"])
def test_managed_camoufox_cancelled_update_keeps_previous_check_record(
    managed_camoufox, stage
):
    from paper_fetch.http import RequestCancelledError

    env = managed_camoufox
    env.query.return_value = [env.old]
    preparation.prepare_camoufox_managed_runtime()
    record = env.check_path.read_bytes()
    env.clock[0] += 86400
    env.query.return_value = [env.latest]
    (
        env.query if stage == "query" else env.download
    ).side_effect = RequestCancelledError("cancelled")
    with pytest.raises(RequestCancelledError):
        preparation.prepare_camoufox_managed_runtime()
    payload = json.loads(env.check_path.read_text())
    assert payload["result"] == "cancelled"
    assert payload["checked_at"] == json.loads(record)["checked_at"]
