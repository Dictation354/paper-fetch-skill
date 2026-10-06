from __future__ import annotations

import json
import os
import sys

import pytest

from paper_fetch.formula import install as formula_install


@pytest.mark.skipif(
    os.name == "nt", reason="Fake Cabal executable uses a POSIX shebang"
)
@pytest.mark.allow_subprocess
@pytest.mark.parametrize("update_failures", [0, 1, 3])
def test_cabal_update_retry_process_contract(
    tmp_path, monkeypatch, capsys, update_failures
):
    cabal = tmp_path / "fake cabal"
    calls_file = tmp_path / "calls.json"
    cabal.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"calls_file = pathlib.Path({str(calls_file)!r})\n"
        "calls = json.loads(calls_file.read_text()) if calls_file.exists() else []\n"
        "calls.append(sys.argv[1:])\n"
        "calls_file.write_text(json.dumps(calls))\n"
        f"if sys.argv[1] == 'update' and len(calls) <= {update_failures}:\n"
        "    print('temporary index failure', file=sys.stderr)\n"
        "    sys.exit(1)\n",
        encoding="utf-8",
    )
    cabal.chmod(0o700)
    monkeypatch.setattr(formula_install.shutil, "which", lambda _: str(cabal))
    monkeypatch.setattr(formula_install.time, "sleep", lambda _: None)
    monkeypatch.setattr(formula_install.tempfile, "tempdir", str(tmp_path))
    target_dir = tmp_path / "formula tools"

    assert formula_install.install_texmath_with_cabal(target_dir) is (
        update_failures < 3
    )

    calls = json.loads(calls_file.read_text())
    updates = [args for args in calls if args[0] == "update"]
    installs = [args for args in calls if args[0] == "install"]
    assert len(updates) == min(update_failures + 1, 3)
    if update_failures < 3:
        assert len(installs) == 1
        assert f"texmath-{formula_install.TEXMATH_VERSION}" in installs[0]
        assert f"--installdir={target_dir / 'bin'}" in installs[0]
    else:
        assert installs == []
    logs = list(tmp_path.glob("texmath-cabal-*.log"))
    assert len(logs) == update_failures
    assert all("temporary index failure" in path.read_text() for path in logs)
    stderr = capsys.readouterr().err
    if update_failures:
        assert "temporary index failure" in stderr
        assert "Build log tail:" in stderr
    else:
        assert stderr == ""


def test_failed_tool_process_keeps_log_and_reports_stderr(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(formula_install.tempfile, "tempdir", str(tmp_path))
    assert not formula_install._run_with_log(
        "formula-failure-",
        [
            sys.executable,
            "-c",
            "import sys; print('compile failed', file=sys.stderr); sys.exit(2)",
        ],
    )
    logs = list(tmp_path.glob("formula-failure-*.log"))
    assert len(logs) == 1
    assert logs[0].read_text() == "compile failed\n"
    assert "compile failed" in capsys.readouterr().err
