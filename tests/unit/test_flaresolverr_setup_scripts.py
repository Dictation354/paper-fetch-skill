from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
FLARESOLVERR_VENDOR_DIR = REPO_ROOT / "vendor" / "flaresolverr"


def _write_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _write_executable(path: Path, content: str) -> None:
    _write_file(path, content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def _create_patched_flaresolverr_repo(root: Path) -> Path:
    repo = root / "FlareSolverr"
    _write_file(repo / "src" / "dtos.py", "returnImagePayload = True\n")
    _write_file(repo / "src" / "flaresolverr_service.py", "imagePayload = {}\n")
    _write_file(repo / "src" / "flaresolverr.py", "print('flaresolverr started')\n")
    _write_file(repo / "requirements.txt")

    subprocess.run(["git", "init", str(repo)], text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _git(repo, "add", ".")
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=paper-fetch-skill",
            "-c",
            "user.email=paper-fetch-skill@example.invalid",
            "commit",
            "-m",
            "seed patched source",
        ],
        text=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return repo


def _prepare_runtime(root: Path) -> tuple[Path, Path, Path]:
    fake_bin = root / "fake-bin"
    _write_executable(fake_bin / "Xvfb", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "python",
        """
        #!/usr/bin/env bash
        if [[ "${1:-}" == "-u" ]]; then
          shift
        fi
        exec python3 "$@"
        """,
    )

    venv = root / "venv"
    _write_file(
        venv / "bin" / "activate",
        f"""
        VIRTUAL_ENV="{venv}"
        PATH="$VIRTUAL_ENV/bin:$PATH"
        export VIRTUAL_ENV PATH
        """,
    )
    _write_executable(venv / "bin" / "pip", "#!/usr/bin/env bash\nexit 0\n")

    downloads = root / "downloads"
    _write_file(downloads / "v3.4.6" / "flaresolverr_linux_x64.tar.gz")
    _write_executable(
        downloads / "v3.4.6" / "flaresolverr" / "_internal" / "chrome" / "chrome",
        "#!/usr/bin/env bash\nexit 0\n",
    )

    return fake_bin, venv, downloads


def _write_env_file(path: Path, *, repo: Path, venv: Path, downloads: Path, headless: str = "true") -> Path:
    _write_file(
        path,
        f"""
        FLARESOLVERR_REPO_DIR="{repo}"
        FLARESOLVERR_VENV_DIR="{venv}"
        FLARESOLVERR_DOWNLOAD_DIR="{downloads}"
        FLARESOLVERR_RELEASE_VERSION="v3.4.6"
        FLARESOLVERR_HOST="127.0.0.1"
        FLARESOLVERR_PORT="8191"
        HEADLESS="{headless}"
        FLARESOLVERR_LOG_FILE="{path.parent / "run.log"}"
        FLARESOLVERR_PID_FILE="{path.parent / "run.pid"}"
        PROBE_OUTPUT_ROOT="{path.parent / "probe_outputs"}"
        """,
    )
    return path


class FlareSolverrSetupScriptTests(unittest.TestCase):
    def test_setup_reuses_patched_checkout_with_tracked_local_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = _create_patched_flaresolverr_repo(root)
            service_file = repo / "src" / "flaresolverr_service.py"
            service_file.write_text(service_file.read_text(encoding="utf-8") + "# user local change\n", encoding="utf-8")
            fake_bin, venv, downloads = _prepare_runtime(root)
            env_file = _write_env_file(root / "flaresolverr.env", repo=repo, venv=venv, downloads=downloads)

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            result = subprocess.run(
                ["bash", str(FLARESOLVERR_VENDOR_DIR / "setup_flaresolverr_source.sh"), str(env_file)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Reusing existing patched FlareSolverr source checkout", result.stdout)
            self.assertIn("# user local change", service_file.read_text(encoding="utf-8"))
            self.assertIn("M src/flaresolverr_service.py", _git(repo, "status", "--short", "--untracked-files=no").stdout)

    def test_run_allows_tracked_local_source_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo = _create_patched_flaresolverr_repo(root)
            service_file = repo / "src" / "flaresolverr_service.py"
            service_file.write_text(service_file.read_text(encoding="utf-8") + "# user local change\n", encoding="utf-8")
            fake_bin, venv, downloads = _prepare_runtime(root)
            env_file = _write_env_file(
                root / "flaresolverr.env",
                repo=repo,
                venv=venv,
                downloads=downloads,
                headless="false",
            )

            env = os.environ.copy()
            env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
            env["DISPLAY"] = ":99"
            result = subprocess.run(
                ["bash", str(FLARESOLVERR_VENDOR_DIR / "run_flaresolverr_source.sh"), str(env_file)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Running FlareSolverr with tracked local source changes", result.stderr)
            self.assertIn("flaresolverr started", result.stdout)


if __name__ == "__main__":
    unittest.main()
