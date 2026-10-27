from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import sys
import tarfile
import threading
from urllib.request import urlopen

import pytest

from paper_fetch import cli, config, update
from tests.support._update_support import installation, release


@pytest.fixture
def release_server(monkeypatch):
    resources = {}
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path not in resources:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(resources[self.path])))
            self.end_headers()
            self.wfile.write(resources[self.path])

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()

    def route(request, **kwargs):
        path = (
            "/latest"
            if request.full_url == update.LATEST_RELEASE_URL
            else "/" + request.full_url.rsplit("/", 1)[1]
        )
        return urlopen(f"http://127.0.0.1:{server.server_port}{path}", **kwargs)

    monkeypatch.setattr(update, "urlopen", route)
    try:
        yield resources, requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def publish(resources, name, payload):
    resources["/latest"] = json.dumps(release(name, "SHA256SUMS")).encode()
    resources["/" + name] = payload
    resources["/SHA256SUMS"] = (
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n".encode()
    )


def prepare_installation(tmp_path, monkeypatch, system):
    tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
    installed = installation(tmp_path / "custom install", system, tag)
    monkeypatch.setattr(
        update,
        "__file__",
        str(installed.root / "runtime/site-packages/paper_fetch/update.py"),
    )
    monkeypatch.setattr(
        update.platform, "system", lambda: "Darwin" if system == "macos" else "Linux"
    )
    monkeypatch.setattr(
        update.platform, "machine", lambda: installed.manifest["target"]["arch"]
    )
    monkeypatch.setattr(update, "package_version", lambda: "7.2.3")
    return installed


@pytest.mark.skipif(os.name == "nt", reason="Unix installer subprocess contract")
@pytest.mark.parametrize("system", ["linux", "macos"])
@pytest.mark.parametrize("external,exit_code", [(False, 0), (True, 0), (True, 7)])
def test_real_installer_process(
    tmp_path, monkeypatch, release_server, capsys, system, external, exit_code
):
    installed = prepare_installation(tmp_path, monkeypatch, system)
    internal_env = installed.root / "offline.env"
    internal_env.write_text('ELSEVIER_API_KEY="keep-secret"\n')
    downloads = installed.root / "downloads"
    downloads.mkdir()
    (downloads / "paper.md").write_text("keep paper")
    state = tmp_path / "auth-state.json"
    state.write_text("keep auth")
    external_env = tmp_path / "external config.env"
    external_env.write_text(
        'PAPER_FETCH_BROWSER_HEADLESS="false"\nWILEY_TDM_CLIENT_TOKEN="keep-token"\n'
    )
    monkeypatch.setattr(config, "DEFAULT_USER_ENV_FILE", tmp_path / "user.env")
    (tmp_path / "user.env").write_text('PAPER_FETCH_BROWSER_HEADLESS="off"\n')
    monkeypatch.delenv("PAPER_FETCH_BROWSER_HEADLESS", raising=False)
    monkeypatch.setenv(
        "PAPER_FETCH_ENV_FILE", str(external_env if external else internal_env)
    )
    report = tmp_path / "installer report.json"
    monkeypatch.setenv("UPDATE_TEST_REPORT", str(report))
    monkeypatch.setenv("PAPER_FETCH_OFFLINE_PYTHON_BIN", "/wrong/python")
    script = f"""#!/usr/bin/env bash
set -eu
"$PAPER_FETCH_OFFLINE_PYTHON_BIN" - "$@" <<'PY'
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
root = Path(args[args.index("--install-dir") + 1])
Path(os.environ["UPDATE_TEST_REPORT"]).write_text(json.dumps({{"args": args, "python": os.environ["PAPER_FETCH_OFFLINE_PYTHON_BIN"]}}))
if {exit_code} == 0:
    (root / "installed-version").write_text("8.0.0")
raise SystemExit({exit_code})
PY
""".encode()
    name = update.installer_asset_name(installed)
    if system == "macos":
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            member = tarfile.TarInfo(
                name.removesuffix(".tar.gz") + "/install-offline.sh"
            )
            member.size = len(script)
            member.mode = 0o755
            archive.addfile(member, io.BytesIO(script))
        payload = stream.getvalue()
    else:
        payload = script
    resources, requests = release_server
    publish(resources, name, payload)
    assert cli.main(["update"]) == (1 if exit_code else 0)
    recorded = json.loads(report.read_text())
    assert recorded["python"] == sys.executable
    expected = [
        "--install-dir",
        str(installed.root),
        "--preset=headful",
        "--non-interactive",
    ]
    if external:
        expected += ["--reuse-env-file", str(external_env)]
    assert recorded["args"] == expected
    assert requests == ["/latest", "/SHA256SUMS", "/" + name]
    assert internal_env.read_text() == 'ELSEVIER_API_KEY="keep-secret"\n'
    assert external_env.read_text().endswith('WILEY_TDM_CLIENT_TOKEN="keep-token"\n')
    assert (downloads / "paper.md").read_text() == "keep paper"
    assert state.read_text() == "keep auth"
    if exit_code:
        assert "退出码 7" in capsys.readouterr().err
    else:
        assert (installed.root / "installed-version").read_text() == "8.0.0"


@pytest.mark.parametrize("failure", [False, True])
def test_windows_wizard_handoff(tmp_path, monkeypatch, release_server, capsys, failure):
    installed = installation(tmp_path / "Windows install", "windows")
    monkeypatch.setattr(update, "find_installation", lambda: installed)
    name = installed.packages["windows_setup_base_name"] + ".exe"
    monkeypatch.setattr(update, "installer_asset_name", lambda _: name)
    monkeypatch.setattr(update, "package_version", lambda: "7.2.3")
    work = tmp_path / "download"
    work.mkdir()
    monkeypatch.setattr(update.tempfile, "mkdtemp", lambda **_: str(work))
    monkeypatch.setattr(update.subprocess, "DETACHED_PROCESS", 8, raising=False)
    monkeypatch.setattr(
        update.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False
    )
    calls = []

    def start(command, **kwargs):
        assert (work / name).read_bytes() == b"verified exe"
        calls.append((command, kwargs))
        if failure:
            raise OSError("cannot open wizard")

    monkeypatch.setattr(update.subprocess, "Popen", start)
    publish(release_server[0], name, b"verified exe")
    assert cli.main(["update"]) == (1 if failure else 0)
    assert calls[0][0] == [str(work / name), f"/DIR={installed.root}"]
    assert calls[0][1]["creationflags"] == 520
    assert calls[0][1]["close_fds"] is True
    assert work.exists() is (not failure)
    if failure:
        assert "cannot open wizard" in capsys.readouterr().err
    else:
        out = capsys.readouterr().out
        assert "已启动安装向导" in out
        assert str(work / name) in out


@pytest.mark.parametrize(
    "kind",
    [
        "absolute",
        "traversal",
        "symlink",
        "hardlink",
        "fifo",
        "duplicate",
        "case",
        "conflict",
        "missing",
    ],
)
def test_macos_archive_preflight_before_extract(tmp_path, kind):
    archive_path = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        valid = tarfile.TarInfo("bundle/install-offline.sh")
        valid.size = 1
        if kind != "missing":
            archive.addfile(valid, io.BytesIO(b"x"))
        bad = tarfile.TarInfo(
            {
                "absolute": "/escape",
                "traversal": "bundle/../escape",
                "duplicate": "bundle/install-offline.sh",
                "case": "bundle/INSTALL-OFFLINE.sh",
                "conflict": "bundle/install-offline.sh/file",
            }.get(kind, "bundle/bad")
        )
        if kind in {"symlink", "hardlink", "fifo"}:
            bad.type = {
                "symlink": tarfile.SYMTYPE,
                "hardlink": tarfile.LNKTYPE,
                "fifo": tarfile.FIFOTYPE,
            }[kind]
            bad.linkname = "../../escape"
        archive.addfile(bad)
    destination = tmp_path / "unpacked"
    with pytest.raises(ValueError):
        update.unpack_macos(archive_path, destination)
    assert not destination.exists()
