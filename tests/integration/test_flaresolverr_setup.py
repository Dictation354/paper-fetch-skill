"""Independent installer mode runs on the installed interpreter without a TTY."""

import os
import subprocess
import sys

import pytest

from paper_fetch.providers.browser_runtime.chrome import supported_platform


@pytest.mark.skipif(
    not supported_platform(), reason="FlareSolverr supports Windows/Linux x64"
)
def test_invalid_explicit_chrome_reports_not_ready_preserving_core(tmp_path):
    core = tmp_path / "installed-core"
    core.write_text("success")
    config = tmp_path / "offline.env"
    config.write_text(f'PAPER_FETCH_CHROME_BINARY_PATH="{tmp_path / "missing"}"\n')
    result_file = tmp_path / "result.txt"
    env = {**os.environ, "PAPER_FETCH_CHROME_BINARY_PATH": str(tmp_path / "missing")}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "paper_fetch.offline_setup",
            "--install-root",
            str(tmp_path),
            "--env-file",
            str(config),
            "--prepare-flaresolverr",
            "--non-interactive",
            "--result",
            str(result_file),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "FlareSolverr: not ready" in result.stdout
    assert "Correct explicit PAPER_FETCH_CHROME_BINARY_PATH" in result_file.read_text()
    assert "Retry:" in result_file.read_text()
    assert core.read_text() == "success"
    assert str(tmp_path / "missing") in config.read_text()
