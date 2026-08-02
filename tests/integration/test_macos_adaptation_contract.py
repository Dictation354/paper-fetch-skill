from __future__ import annotations

import subprocess
import sys

from tests.paths import REPO_ROOT


def test_cross_platform_validator_accepts_repository_contract() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_macos_adaptation.py"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "macOS adaptation contract OK" in result.stdout
    assert "paper-fetch/macos v4.1.0" in result.stdout


def test_contract_surface_node_cli_supports_windows_and_wsl() -> None:
    for surface in ("windows", "wsl"):
        result = subprocess.run(
            [
                sys.executable,
                "scripts/validate_macos_adaptation.py",
                "--print-test-nodes",
                surface,
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines()
