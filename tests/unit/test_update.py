from __future__ import annotations

import hashlib
import io
import json
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import URLError

import pytest

from paper_fetch import cli, update
from tests.support._update_support import installation, release


def test_update_help_and_dispatch(monkeypatch, capsys):
    with pytest.raises(SystemExit) as error:
        cli.main(["update", "--help"])
    assert error.value.code == 0
    assert "latest stable Release" in capsys.readouterr().out
    assert "update" in cli.build_parser().format_help()
    monkeypatch.setattr(update, "run_update", lambda: 0)
    assert cli.main(["update"]) == 0


@pytest.mark.parametrize(
    "older,newer",
    [
        ("7.2.3", "v7.2.4"),
        ("7.9.9", "7.10.0"),
        ("7.2.3", "8.0.0"),
        ("8.0.0.dev1", "8.0.0a1"),
        ("8.0.0a1", "8.0.0b1"),
        ("8.0.0b1", "8.0.0rc1"),
        ("8.0.0rc2", "8.0.0"),
        ("8.0.0", "8.0.0.post1"),
        ("8.0.0rc1.dev1", "8.0.0rc1"),
    ],
)
def test_versions(older, newer):
    assert update.version_key(older) < update.version_key(newer)


def test_version_equality_and_invalid():
    assert update.version_key("v8.0.0") == update.version_key("8.0.0+local")
    with pytest.raises(ValueError, match="版本"):
        update.version_key("unknown")


@pytest.mark.parametrize(
    "system,host,arch,tag,expected",
    [
        *[
            (
                "linux",
                "Linux",
                "AMD64",
                f"cp3{minor}",
                f"paper-fetch-skill-offline-linux-x86_64-cp3{minor}.sh",
            )
            for minor in range(11, 15)
        ],
        *[
            (
                "macos",
                "Darwin",
                "aarch64",
                f"cp3{minor}",
                f"paper-fetch-skill-offline-macos-arm64-cp3{minor}.tar.gz",
            )
            for minor in range(11, 15)
        ],
        (
            "windows",
            "Windows",
            "AMD64",
            "cp313",
            "paper-fetch-skill-windows-x86_64-setup.exe",
        ),
    ],
)
def test_release_targets(tmp_path, monkeypatch, system, host, arch, tag, expected):
    monkeypatch.setattr(update, "sys", SimpleNamespace(**vars(update.sys)))
    installed = installation(tmp_path / "installed", system, tag)
    monkeypatch.setattr(update.platform, "system", lambda: host)
    monkeypatch.setattr(update.platform, "machine", lambda: arch)
    monkeypatch.setattr(
        update.sys, "version_info", SimpleNamespace(major=3, minor=int(tag[3:]))
    )
    monkeypatch.setattr(update.sys, "abiflags", "", raising=False)
    monkeypatch.setattr(
        update.sysconfig,
        "get_config_var",
        lambda key: f"cpython-{tag[2:]}-test" if key == "SOABI" else 0,
    )
    assert update.installer_asset_name(installed) == expected


@pytest.mark.parametrize(
    "problem", ["arch", "tag", "free_threaded", "debug", "soabi", "implementation"]
)
def test_incompatible_target(tmp_path, monkeypatch, problem):
    monkeypatch.setattr(update, "sys", SimpleNamespace(**vars(update.sys)))
    installed = installation(
        tmp_path / "installed",
        tag=f"cp{update.sys.version_info.major}{update.sys.version_info.minor}",
    )
    monkeypatch.setattr(update.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        update.platform, "machine", lambda: "arm64" if problem == "arch" else "x86_64"
    )
    if problem == "tag":
        installed.manifest["target"]["python_tag"] = "cp399"
    monkeypatch.setattr(
        update.sys, "abiflags", "d" if problem == "debug" else "", raising=False
    )
    if problem == "implementation":
        monkeypatch.setattr(update.sys, "implementation", SimpleNamespace(name="pypy"))
    original = update.sysconfig.get_config_var
    monkeypatch.setattr(
        update.sysconfig,
        "get_config_var",
        lambda key: (
            (1 if problem == "free_threaded" else 0)
            if key == "Py_GIL_DISABLED"
            else ("invalid" if problem == "soabi" else original(key))
        ),
    )
    with pytest.raises(ValueError):
        update.installer_asset_name(installed)


@pytest.mark.parametrize(
    "system,site",
    [
        ("linux", "site-packages"),
        ("macos", "site-packages"),
        ("windows", "Lib/site-packages"),
    ],
)
def test_find_official_installation(tmp_path, monkeypatch, system, site):
    installed = installation(tmp_path / "custom directory", system)
    monkeypatch.setattr(
        update,
        "__file__",
        str(installed.root / "runtime" / site / "paper_fetch/update.py"),
    )
    assert update.find_installation() == installed
    installed.manifest["project"] = "other"
    (installed.root / "offline-manifest.json").write_text(
        json.dumps(installed.manifest)
    )
    with pytest.raises(ValueError, match="官方"):
        update.find_installation()


@pytest.mark.parametrize("source", [True, False])
def test_unsupported_installation_has_existing_command(
    tmp_path, monkeypatch, capsys, source
):
    module = tmp_path / ("src" if source else "site-packages") / "paper_fetch/update.py"
    if source:
        (tmp_path / "pyproject.toml").touch()
    monkeypatch.setattr(update, "__file__", str(module))
    request = Mock()
    monkeypatch.setattr(update, "urlopen", request)
    assert update.run_update() == 1
    error = capsys.readouterr().err
    assert "pip install --upgrade" in error
    assert ("git pull" in error) == source
    request.assert_not_called()


@pytest.mark.parametrize("current", ["8.0.0", "8.1.0", "10.0.0"])
def test_current_or_newer_skips_download(tmp_path, monkeypatch, capsys, current):
    monkeypatch.setattr(
        update, "find_installation", lambda: installation(tmp_path / "installed")
    )
    monkeypatch.setattr(update, "installer_asset_name", lambda _: "installer.sh")
    monkeypatch.setattr(update, "latest_release", lambda: release())
    monkeypatch.setattr(update, "package_version", lambda: current)
    download = Mock()
    monkeypatch.setattr(update, "download", download)
    assert update.run_update() == 0
    assert "已是最新或更新" in capsys.readouterr().out
    download.assert_not_called()


def test_release_request_and_pinning(monkeypatch):
    response = Mock(
        side_effect=lambda *_a, **_k: io.BytesIO(
            json.dumps(release("installer.sh", "SHA256SUMS")).encode()
        )
    )
    monkeypatch.setattr(update, "urlopen", response)
    result = update.latest_release()
    assert response.call_count == 1
    request = response.call_args.args[0]
    assert request.full_url == update.LATEST_RELEASE_URL
    assert request.get_header("Accept") == "application/vnd.github+json"
    assert "/v8.0.0/" in update.release_asset_url(result, "installer.sh")


@pytest.mark.parametrize(
    "payload",
    [{}, [], {"draft": True}, {"prerelease": True}, {"tag_name": "v8.0.0rc1"}],
)
def test_invalid_release(monkeypatch, payload):
    monkeypatch.setattr(
        update, "urlopen", lambda *_a, **_k: io.BytesIO(json.dumps(payload).encode())
    )
    with pytest.raises(ValueError):
        update.latest_release()


def test_missing_duplicate_and_wrong_release_assets():
    with pytest.raises(ValueError, match="缺少"):
        update.release_asset_url(release(), "installer.sh")
    with pytest.raises(ValueError, match="唯一"):
        update.release_asset_url(
            release("installer.sh", "installer.sh"), "installer.sh"
        )
    payload = release("installer.sh")
    payload["assets"][0]["browser_download_url"] = (
        "https://github.com/other/repo/releases/latest/download/installer.sh"
    )
    with pytest.raises(ValueError, match="地址"):
        update.release_asset_url(payload, "installer.sh")


def test_streaming_download_and_checksum(tmp_path, monkeypatch):
    content = b"payload" * 400_000
    monkeypatch.setattr(update, "urlopen", lambda *_a, **_k: io.BytesIO(content))
    destination = tmp_path / "installer.sh"
    digest = update.download("https://example.test/installer.sh", destination)
    assert digest == hashlib.sha256(content).hexdigest()
    assert destination.read_bytes() == content
    sums = tmp_path / "SHA256SUMS"
    sums.write_text(f"{digest}  installer.sh\n")
    update.verify_checksum(sums, destination.name, digest)
    sums.write_text(f"{digest} *installer.sh\n")
    update.verify_checksum(sums, destination.name, digest)
    for text in [
        "",
        f"{'0' * 64}  installer.sh\n",
        f"{digest}  other.sh\n",
        f"{digest}  installer.sh\n" * 2,
    ]:
        sums.write_text(text)
        with pytest.raises(ValueError, match="SHA256"):
            update.verify_checksum(sums, destination.name, digest)


@pytest.mark.parametrize("failure", ["query", "missing", "download", "digest"])
def test_update_errors_never_execute_installer(tmp_path, monkeypatch, capsys, failure):
    installed = installation(tmp_path / "installed")
    monkeypatch.setattr(update, "find_installation", lambda: installed)
    monkeypatch.setattr(update, "installer_asset_name", lambda _: "installer.sh")
    monkeypatch.setattr(update, "package_version", lambda: "7.2.3")
    monkeypatch.setattr(
        update,
        "latest_release",
        Mock(side_effect=URLError("query failed"))
        if failure == "query"
        else lambda: release(
            *([] if failure == "missing" else ["installer.sh", "SHA256SUMS"])
        ),
    )
    work = tmp_path / "download"
    work.mkdir()
    monkeypatch.setattr(update.tempfile, "mkdtemp", lambda **_: str(work))

    def download(_url, path):
        if failure == "download":
            raise URLError("download failed")
        path.write_bytes(b"bad checksum")
        return "0" * 64

    monkeypatch.setattr(update, "download", download)
    execute = Mock()
    monkeypatch.setattr(update.subprocess, "run", execute)
    assert update.run_update() == 1
    assert "更新失败" in capsys.readouterr().err
    execute.assert_not_called()
    if failure in {"download", "digest"}:
        assert not work.exists()
