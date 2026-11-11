"""Official archive layouts and independent Node staging contracts."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from zipfile import ZipFile

import pytest

from scripts.build_node_runtime import stage_node_runtime
from tests.support._installer_support import write_posix_command_wrappers


@pytest.mark.parametrize(
    "target", ["linux_node_x86_64", "macos_node_arm64", "windows_node_x86_64"]
)
def test_node_archive_stages_only_executable_license_and_provenance(tmp_path, target):
    pins = json.loads(
        (Path(__file__).resolve().parents[2] / "installer/manifest.json").read_text()
    )
    pin = pins["embedded_runtimes"][target]
    source = tmp_path / pin["archive"]
    payload = {
        f"{pin['archive_root']}/{pin['executable']}": b"node executable",
        f"{pin['archive_root']}/LICENSE": b"Node and third-party licenses",
        f"{pin['archive_root']}/include/unused.h": b"unused",
    }
    if source.suffix == ".zip":
        with ZipFile(source, "w") as archive:
            for name, data in payload.items():
                archive.writestr(name, data)
    else:
        with tarfile.open(source, "w:gz") as archive:
            for name, data in payload.items():
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
    pin["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    pin["url"] = source.as_uri()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(pins))
    staging = tmp_path / "staged runtime"
    cache = tmp_path / "archive cache"
    record = stage_node_runtime(
        staging, target=target, manifest_path=manifest, cache_dir=cache
    )
    executable = staging / "runtime/node" / pin["executable"]
    assert executable.read_bytes() == b"node executable"
    if os.name != "nt":
        assert executable.stat().st_mode & 0o111
    assert (
        staging / "runtime/node/LICENSE"
    ).read_bytes() == b"Node and third-party licenses"
    assert not (staging / "runtime/node/include").exists()
    assert record["version"] == "26.13.0"
    assert record["actual_sha256"] == record["expected_sha256"] == pin["sha256"]
    assert (
        json.loads((staging / "runtime/node/node-runtime.json").read_text()) == record
    )

    (cache / pin["archive"]).write_bytes(b"corrupt archive")
    with pytest.raises(ValueError, match="Node archive SHA-256 mismatch"):
        stage_node_runtime(
            tmp_path / "rejected",
            target=target,
            manifest_path=manifest,
            cache_dir=cache,
        )
    assert not (tmp_path / "rejected").exists()


def test_independent_node_drives_playwright_and_exits():
    pytest.importorskip("playwright")
    node = os.environ.get("PLAYWRIGHT_NODEJS_PATH") or shutil.which("node")
    if not node:
        pytest.skip("requires Node.js")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
with sync_playwright() as driver:
    process = driver._impl_obj._connection._transport._proc
    assert driver.chromium.name == 'chromium'
assert process.returncode == 0
async def check():
    async with async_playwright() as driver:
        process = driver._impl_obj._connection._transport._proc
        assert driver.firefox.name == 'firefox'
    assert process.returncode == 0
asyncio.run(check())
""",
        ],
        env={**os.environ, "PLAYWRIGHT_NODEJS_PATH": node},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX release launcher contract")
@pytest.mark.parametrize("override", [False, True])
def test_release_launchers_default_to_independent_node_and_preserve_overrides(
    tmp_path, override
):
    staging = tmp_path / "install with spaces"
    write_posix_command_wrappers(staging)
    python = tmp_path / "record-python"
    python.write_text(
        f"#!{sys.executable}\nimport json, os\n"
        "print(json.dumps({key: os.environ[key] for key in ('MATHML_TO_LATEX_NODE_BIN', 'PLAYWRIGHT_NODEJS_PATH')}))\n"
    )
    python.chmod(0o755)
    (staging / "runtime/python-bin").write_text(str(python) + "\n")
    keys = ("MATHML_TO_LATEX_NODE_BIN", "PLAYWRIGHT_NODEJS_PATH")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in (*keys, "PAPER_FETCH_OFFLINE_PYTHON_BIN")
    }
    expected = {key: str(staging / "runtime/node/bin/node") for key in keys}
    if override:
        expected = {key: f"/custom/{key}/node" for key in keys}
        env.update(expected)
    for name in ("paper-fetch", "paper-fetch-mcp"):
        output = subprocess.check_output(
            [str(staging / "bin" / name), "--help"], env=env, text=True
        )
        assert json.loads(output) == expected


def test_formula_transitive_brace_expansion_and_sre_cli():
    from tests.paths import REPO_ROOT

    workspace = REPO_ROOT / ".formula-tools"
    node = shutil.which("node")
    if not node or not (workspace / "node_modules/speech-rule-engine").is_dir():
        pytest.skip("requires prepared formula Node dependencies")
    braces = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            """
import assert from 'node:assert/strict';
import {expand} from 'brace-expansion';
import {minimatch} from 'minimatch';
assert.deepEqual(expand('x{a,{b,c}}{1..2}'), ['xa1','xa2','xb1','xb2','xc1','xc2']);
assert(minimatch('xb2', 'x{a,{b,c}}{1..2}'));
""",
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert braces.returncode == 0, braces.stderr
    sre = subprocess.run(
        [node, str(workspace / "node_modules/speech-rule-engine/bin/sre"), "--help"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert sre.returncode == 0, sre.stderr
    assert "Usage:" in sre.stdout
