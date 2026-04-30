from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
WINDOWS_INSTALLER = REPO_ROOT / "install-offline.ps1"


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _python_tag(version: str) -> str:
    major, minor, _micro = version.split(".")
    return f"cp{major}{minor}"


def _fake_python_script(version: str) -> str:
    tag = _python_tag(version)
    return f"""\
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION="{version}"
    TAG="{tag}"

    if [[ "${{1:-}}" == "-c" ]]; then
      code="${{2:-}}"
      if [[ "$code" == *'join(map(str, sys.version_info[:3]))'* ]]; then
        echo "$VERSION"
        exit 0
      fi
      if [[ "$code" == *'cp{{sys.version_info.major}}{{sys.version_info.minor}}'* ]]; then
        echo "$TAG"
        exit 0
      fi
      if [[ "$code" == *'json.load'* && "$code" == *'python_tag'* ]]; then
        manifest="${{3:-}}"
        if [[ -f "$manifest" ]]; then
          grep -oE '"python_tag"[[:space:]]*:[[:space:]]*"[^"]+"' "$manifest" | head -n 1 | sed -E 's/.*"python_tag"[[:space:]]*:[[:space:]]*"([^"]+)".*/\\1/'
        fi
        exit 0
      fi
      if [[ "$code" == *'playwright.sync_api'* ]]; then
        echo "${{PLAYWRIGHT_BROWSERS_PATH}}/chromium-123/chrome-linux/chrome"
        exit 0
      fi
      exit 0
    fi

    if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "venv" ]]; then
      venv_dir="$3"
      mkdir -p "$venv_dir/bin"
      cp "$0" "$venv_dir/bin/python"
      chmod +x "$venv_dir/bin/python"
      cat > "$venv_dir/bin/paper-fetch" <<'SH'
    #!/usr/bin/env bash
    if [[ "${1:-}" == "--help" ]]; then
      exit 0
    fi
    exit 0
    SH
      chmod +x "$venv_dir/bin/paper-fetch"
      exit 0
    fi

    if [[ "${{1:-}}" == "-m" && "${{2:-}}" == "pip" ]]; then
      exit 0
    fi

    exit 0
    """


def _write_checksums(root: Path) -> None:
    lines: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name != "sha256sums.txt"):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(root).as_posix()
        lines.append(f"{digest}  ./{relative}\n")
    (root / "sha256sums.txt").write_text("".join(lines), encoding="utf-8")


class OfflineInstallTests(unittest.TestCase):
    def _create_bundle(
        self,
        root: Path,
        *,
        python_version: str = "3.11.9",
        manifest_python_tag: str | None = None,
        include_xvfb: bool = True,
    ) -> tuple[Path, Path, Path]:
        bundle = root / "bundle"
        bundle.mkdir()
        shutil.copy2(REPO_ROOT / "install-offline.sh", bundle / "install-offline.sh")
        (bundle / "install-offline.sh").chmod(0o755)

        manifest_python_tag = manifest_python_tag or _python_tag(python_version)
        _write_file(
            bundle / "offline-manifest.json",
            f'{{"target": {{"platform": "linux", "arch": "x86_64", "python_tag": "{manifest_python_tag}"}}}}\n',
        )
        _write_file(bundle / ".env.example", 'ELSEVIER_API_KEY=""\n')
        _write_file(bundle / "dist" / "paper_fetch_skill-1.0.0-py3-none-any.whl")
        _write_file(bundle / "wheelhouse" / "dependency-1.0.0-py3-none-any.whl")
        _write_executable(
            bundle / "ms-playwright" / "chromium-123" / "chrome-linux" / "chrome",
            "#!/usr/bin/env bash\nexit 0\n",
        )
        _write_executable(bundle / "formula-tools" / "bin" / "texmath", "#!/usr/bin/env bash\nexit 0\n")

        flaresolverr = bundle / "vendor" / "flaresolverr"
        _write_file(flaresolverr / ".env.flaresolverr-source-headless", 'HEADLESS="true"\n')
        _write_file(flaresolverr / ".env.flaresolverr-source-wslg", 'HEADLESS="false"\n')
        _write_file(flaresolverr / ".work" / "FlareSolverr" / "src" / "flaresolverr.py")
        _write_file(flaresolverr / ".work" / "FlareSolverr" / "requirements.txt", "dependency==1.0.0\n")
        _write_file(flaresolverr / "wheelhouse" / "dependency-1.0.0-py3-none-any.whl")
        _write_executable(
            flaresolverr / ".flaresolverr" / "v3.4.6" / "flaresolverr" / "_internal" / "chrome" / "chrome",
            "#!/usr/bin/env bash\nexit 0\n",
        )
        _write_file(
            flaresolverr / "flaresolverr_source_common.sh",
            """
            flaresolverr_source_load_env() { :; }
            flaresolverr_source_ensure_chrome_link() { :; }
            """,
        )
        for name in (
            "setup_flaresolverr_source.sh",
            "start_flaresolverr_source.sh",
            "run_flaresolverr_source.sh",
            "stop_flaresolverr_source.sh",
        ):
            _write_executable(flaresolverr / name, "#!/usr/bin/env bash\nexit 0\n")

        fake_bin = root / "fake-bin"
        _write_executable(fake_bin / "python3", _fake_python_script(python_version))
        if include_xvfb:
            _write_executable(fake_bin / "Xvfb", "#!/usr/bin/env bash\nexit 0\n")

        _write_checksums(bundle)
        home = root / "home"
        home.mkdir()
        return bundle, fake_bin, home

    def _run_installer(
        self,
        bundle: Path,
        fake_bin: Path,
        home: Path,
        *args: str,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
        env["PAPER_FETCH_OFFLINE_PYTHON_BIN"] = str(fake_bin / "python3")
        env["PAPER_FETCH_OFFLINE_XVFB_BIN"] = str(fake_bin / "Xvfb")
        return subprocess.run(
            [str(bundle / "install-offline.sh"), "--skip-smoke", *args],
            cwd=bundle,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_default_install_writes_local_env_without_touching_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            user_env = home / ".config" / "paper-fetch" / ".env"
            _write_file(user_env, 'ELSEVIER_API_KEY="secret"\n')

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(user_env.read_text(encoding="utf-8"), 'ELSEVIER_API_KEY="secret"\n')
            offline_env = (bundle / "offline.env").read_text(encoding="utf-8")
            self.assertIn("FLARESOLVERR_ENV_FILE=", offline_env)
            self.assertIn(str(bundle / "ms-playwright"), offline_env)
            self.assertNotIn(str(home / ".cache" / "ms-playwright"), offline_env)
            self.assertIn("Elsevier setup: request a key at https://dev.elsevier.com/", result.stdout)
            self.assertIn('ELSEVIER_API_KEY="..."', result.stdout)
            self.assertIn(str(bundle / "offline.env"), result.stdout)

    def test_user_config_merge_preserves_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            user_env = home / ".config" / "paper-fetch" / ".env"
            _write_file(user_env, 'ELSEVIER_API_KEY="secret"\n')

            result = self._run_installer(bundle, fake_bin, home, "--user-config")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = user_env.read_text(encoding="utf-8")
            self.assertIn('ELSEVIER_API_KEY="secret"', payload)
            self.assertIn("# BEGIN paper-fetch offline managed", payload)
            self.assertIn(str(bundle / "vendor" / "flaresolverr"), payload)

    def test_matching_manifest_and_interpreter_tags_are_accepted(self) -> None:
        cases = (
            ("3.11.9", "cp311"),
            ("3.12.7", "cp312"),
            ("3.13.3", "cp313"),
            ("3.14.0", "cp314"),
        )
        for python_version, python_tag in cases:
            with self.subTest(python_tag=python_tag), tempfile.TemporaryDirectory() as tmpdir:
                bundle, fake_bin, home = self._create_bundle(
                    Path(tmpdir),
                    python_version=python_version,
                    manifest_python_tag=python_tag,
                )

                result = self._run_installer(bundle, fake_bin, home)

                self.assertEqual(result.returncode, 0, result.stderr)

    def test_mismatched_manifest_and_interpreter_tag_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(
                Path(tmpdir),
                python_version="3.12.1",
                manifest_python_tag="cp313",
            )

            result = self._run_installer(bundle, fake_bin, home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bundle requires CPython cp313", result.stderr)
            self.assertIn("detected Python 3.12.1 (cp312)", result.stderr)

    def test_missing_xvfb_has_clear_headless_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir), include_xvfb=False)

            result = self._run_installer(bundle, fake_bin, home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Xvfb is required", result.stderr)

    def test_repeated_install_keeps_single_managed_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            first = self._run_installer(bundle, fake_bin, home)
            second = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            offline_env = (bundle / "offline.env").read_text(encoding="utf-8")
            self.assertEqual(offline_env.count("# BEGIN paper-fetch offline managed"), 1)
            self.assertEqual(offline_env.count("# END paper-fetch offline managed"), 1)

    def test_windows_installer_declares_abi_checksum_and_asset_guards(self) -> None:
        script = WINDOWS_INSTALLER.read_text(encoding="utf-8")

        self.assertIn("target.python_tag", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("PIP_NO_INDEX", script)
        self.assertIn("formula-tools/bin/texmath.exe", script)
        self.assertIn("ms-playwright", script)
        self.assertIn("flaresolverr.exe", script)
        self.assertIn("chrome.exe", script)
        self.assertIn("$NoUserConfig", script)

    def test_windows_installer_writes_managed_env_and_activation_script(self) -> None:
        script = WINDOWS_INSTALLER.read_text(encoding="utf-8")

        self.assertIn("# BEGIN paper-fetch offline managed", script)
        self.assertIn("# END paper-fetch offline managed", script)
        self.assertIn("Activate-Offline.ps1", script)
        self.assertIn("PAPER_FETCH_FORMULA_TOOLS_DIR", script)
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH", script)
        self.assertIn("FLARESOLVERR_SOURCE_DIR", script)
        self.assertIn("ELSEVIER_API_KEY", script)
        self.assertIn("https://dev.elsevier.com/", script)
        self.assertNotIn(".cache/ms-playwright'", script)

    def test_windows_installer_smoke_checks_do_not_use_user_playwright_cache(self) -> None:
        script = WINDOWS_INSTALLER.read_text(encoding="utf-8")

        self.assertIn("provider_status_payload", script)
        self.assertIn("manager.chromium.executable_path", script)
        self.assertIn("assert root in executable.parents", script)
        self.assertIn("paper-fetch.exe", script)

    def test_windows_installer_platform_check_supports_windows_powershell_51(self) -> None:
        script = WINDOWS_INSTALLER.read_text(encoding="utf-8")
        start = script.index("function Test-RunningOnWindowsPlatform")
        end = script.index("function Invoke-PythonText", start)
        block = script[start:end]

        self.assertIn("PROCESSOR_ARCHITEW6432", block)
        self.assertIn("PROCESSOR_ARCHITECTURE", block)
        self.assertIn('if ($arch -ne "AMD64")', block)
        self.assertNotIn("OSArchitecture", block)
        self.assertNotIn("RuntimeInformation", block)


if __name__ == "__main__":
    unittest.main()
