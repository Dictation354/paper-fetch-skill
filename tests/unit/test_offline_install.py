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
WINDOWS_INSTALLER_HELPER = REPO_ROOT / "scripts" / "windows-installer-helper.ps1"


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_recording_cli(path: Path, log_path: Path, *, exit_code: int = 0) -> None:
    _write_executable(
        path,
        f"""\
        #!/usr/bin/env bash
        {{
          printf '%s' "$(basename "$0")"
          for arg in "$@"; do
            printf '\\t%s' "$arg"
          done
          printf '\\n'
        }} >> "{log_path}"
        exit {exit_code}
        """,
    )


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
      cat > "$venv_dir/bin/paper-fetch-mcp" <<'SH'
    #!/usr/bin/env bash
    exit 0
    SH
      chmod +x "$venv_dir/bin/paper-fetch-mcp"
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
        _write_file(bundle / "skills" / "paper-fetch-skill" / "SKILL.md", "# Paper fetch skill\n")
        _write_file(
            bundle / "skills" / "paper-fetch-skill" / "references" / "tool-contract.md",
            "Tool contract\n",
        )
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
        shell: str | None = "/bin/bash",
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PATH"] = f"{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin"
        env["PAPER_FETCH_OFFLINE_PYTHON_BIN"] = str(fake_bin / "python3")
        env["PAPER_FETCH_OFFLINE_XVFB_BIN"] = str(fake_bin / "Xvfb")
        if shell is None:
            env.pop("SHELL", None)
        else:
            env["SHELL"] = shell
        if extra_env:
            env.update(extra_env)
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

    def test_default_install_copies_codex_and_claude_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            codex_skill = home / ".codex" / "skills" / "paper-fetch-skill"
            claude_skill = home / ".claude" / "skills" / "paper-fetch-skill"
            self.assertEqual((codex_skill / "SKILL.md").read_text(encoding="utf-8"), "# Paper fetch skill\n")
            self.assertEqual((claude_skill / "SKILL.md").read_text(encoding="utf-8"), "# Paper fetch skill\n")
            self.assertTrue((codex_skill / "references" / "tool-contract.md").is_file())
            self.assertTrue((claude_skill / "references" / "tool-contract.md").is_file())

    def test_bash_shell_startup_file_uses_managed_runtime_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home, shell="/bin/bash")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = (home / ".bashrc").read_text(encoding="utf-8")
            self.assertEqual(payload.count("# BEGIN paper-fetch offline managed"), 1)
            self.assertIn(
                f'export PATH="{bundle / ".venv" / "bin"}":"{bundle / "formula-tools" / "bin"}":$PATH',
                payload,
            )
            self.assertIn(f'export PAPER_FETCH_ENV_FILE="{bundle / "offline.env"}"', payload)
            self.assertIn(f'export PAPER_FETCH_FORMULA_TOOLS_DIR="{bundle / "formula-tools"}"', payload)
            self.assertIn(f'export PLAYWRIGHT_BROWSERS_PATH="{bundle / "ms-playwright"}"', payload)
            self.assertIn(f'export FLARESOLVERR_SOURCE_DIR="{bundle / "vendor" / "flaresolverr"}"', payload)
            self.assertIn(
                f'export FLARESOLVERR_ENV_FILE="{bundle / "vendor" / "flaresolverr" / ".env.flaresolverr-source-headless"}"',
                payload,
            )
            self.assertIn('export FLARESOLVERR_URL="http://127.0.0.1:8191/v1"', payload)

    def test_zsh_shell_startup_file_uses_zshrc(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home, shell="/bin/zsh")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = (home / ".zshrc").read_text(encoding="utf-8")
            self.assertEqual(payload.count("# BEGIN paper-fetch offline managed"), 1)
            self.assertIn(f'export PAPER_FETCH_ENV_FILE="{bundle / "offline.env"}"', payload)
            self.assertFalse((home / ".bashrc").exists())

    def test_fish_shell_startup_file_uses_fish_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home, shell="/usr/bin/fish")

            self.assertEqual(result.returncode, 0, result.stderr)
            fish_config = home / ".config" / "fish" / "conf.d" / "paper-fetch-offline.fish"
            payload = fish_config.read_text(encoding="utf-8")
            self.assertEqual(payload.count("# BEGIN paper-fetch offline managed"), 1)
            self.assertIn(
                f'set -gx PATH "{bundle / ".venv" / "bin"}" "{bundle / "formula-tools" / "bin"}" $PATH',
                payload,
            )
            self.assertIn(f'set -gx PAPER_FETCH_ENV_FILE "{bundle / "offline.env"}"', payload)
            self.assertIn(f'set -gx PLAYWRIGHT_BROWSERS_PATH "{bundle / "ms-playwright"}"', payload)
            self.assertFalse((home / ".bashrc").exists())

    def test_unrecognized_shell_falls_back_to_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home, shell="/opt/custom-shell")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = (home / ".profile").read_text(encoding="utf-8")
            self.assertEqual(payload.count("# BEGIN paper-fetch offline managed"), 1)
            self.assertIn(f'export PAPER_FETCH_ENV_FILE="{bundle / "offline.env"}"', payload)
            self.assertIn("Unrecognized SHELL=/opt/custom-shell", result.stderr)

    def test_codex_and_claude_cli_registration_uses_offline_runtime_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            cli_log = root / "cli.log"
            _write_recording_cli(fake_bin / "codex", cli_log)
            _write_recording_cli(fake_bin / "claude", cli_log)

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = [line.split("\t") for line in cli_log.read_text(encoding="utf-8").splitlines()]
            self.assertIn(["codex", "mcp", "remove", "paper-fetch"], calls)
            self.assertIn(["claude", "mcp", "remove", "-s", "user", "paper-fetch"], calls)

            codex_add = next(call for call in calls if call[:3] == ["codex", "mcp", "add"])
            self.assertIn("--env", codex_add)
            self.assertIn(f"PAPER_FETCH_ENV_FILE={bundle / 'offline.env'}", codex_add)
            self.assertIn(f"PAPER_FETCH_MCP_PYTHON_BIN={bundle / '.venv' / 'bin' / 'python'}", codex_add)
            self.assertIn(f"PAPER_FETCH_FORMULA_TOOLS_DIR={bundle / 'formula-tools'}", codex_add)
            self.assertIn(f"PLAYWRIGHT_BROWSERS_PATH={bundle / 'ms-playwright'}", codex_add)
            self.assertIn(f"FLARESOLVERR_SOURCE_DIR={bundle / 'vendor' / 'flaresolverr'}", codex_add)
            self.assertEqual(
                codex_add[-7:],
                [
                    "paper-fetch",
                    "--",
                    str(bundle / ".venv" / "bin" / "python"),
                    "-X",
                    "utf8",
                    "-m",
                    "paper_fetch.mcp.server",
                ],
            )

            claude_add = next(call for call in calls if call[:5] == ["claude", "mcp", "add", "-s", "user"])
            self.assertIn("-e", claude_add)
            self.assertIn(f"PAPER_FETCH_ENV_FILE={bundle / 'offline.env'}", claude_add)
            self.assertEqual(
                claude_add[-7:],
                [
                    "paper-fetch",
                    "--",
                    str(bundle / ".venv" / "bin" / "python"),
                    "-X",
                    "utf8",
                    "-m",
                    "paper_fetch.mcp.server",
                ],
            )
            self.assertFalse((home / ".codex" / "config.toml").exists())

    def test_missing_codex_cli_writes_config_toml_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            config = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("# BEGIN paper-fetch installer managed", config)
            self.assertIn("[mcp_servers.paper-fetch]", config)
            self.assertIn(f'command = "{bundle / ".venv" / "bin" / "python"}"', config)
            self.assertIn('args = ["-X", "utf8", "-m", "paper_fetch.mcp.server"]', config)
            self.assertIn("[mcp_servers.paper-fetch.env]", config)
            self.assertIn(f'PAPER_FETCH_ENV_FILE = "{bundle / "offline.env"}"', config)
            self.assertIn(f'PAPER_FETCH_FORMULA_TOOLS_DIR = "{bundle / "formula-tools"}"', config)
            self.assertIn(f'PLAYWRIGHT_BROWSERS_PATH = "{bundle / "ms-playwright"}"', config)
            self.assertIn(f'FLARESOLVERR_SOURCE_DIR = "{bundle / "vendor" / "flaresolverr"}"', config)
            self.assertIn("Claude CLI not found; installed the skill and skipped Claude MCP registration", result.stdout)

    def test_reuse_env_file_keeps_file_untouched_and_points_runtime_at_new_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            reused_env = root / "shared" / "offline.env"
            reused_payload = textwrap.dedent(
                """
                ELSEVIER_API_KEY="secret"

                # BEGIN paper-fetch offline managed
                PAPER_FETCH_DOWNLOAD_DIR="/old-bundle/downloads"
                FLARESOLVERR_SOURCE_DIR="/old-bundle/vendor/flaresolverr"
                # END paper-fetch offline managed
                """
            ).lstrip()
            _write_file(reused_env, reused_payload)

            result = self._run_installer(bundle, fake_bin, home, "--reuse-env-file", str(reused_env))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(reused_env.read_text(encoding="utf-8"), reused_payload)
            self.assertFalse((bundle / "offline.env").exists())
            self.assertIn(f"Reusing offline.env without modifying it: {reused_env}", result.stdout)

            bashrc = (home / ".bashrc").read_text(encoding="utf-8")
            self.assertIn(f'export PAPER_FETCH_ENV_FILE="{reused_env}"', bashrc)
            self.assertIn(f'export PAPER_FETCH_DOWNLOAD_DIR="{bundle / "downloads"}"', bashrc)

            config = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn(f'PAPER_FETCH_ENV_FILE = "{reused_env}"', config)
            self.assertIn(f'PAPER_FETCH_DOWNLOAD_DIR = "{bundle / "downloads"}"', config)
            self.assertIn(f'FLARESOLVERR_SOURCE_DIR = "{bundle / "vendor" / "flaresolverr"}"', config)

            probe = subprocess.run(
                [
                    "bash",
                    "-lc",
                    (
                        f'source "{bundle / "activate-offline.sh"}"; '
                        'printf "%s\\n%s\\n%s\\n" '
                        '"$PAPER_FETCH_ENV_FILE" "$PAPER_FETCH_DOWNLOAD_DIR" "$FLARESOLVERR_SOURCE_DIR"'
                    ),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertEqual(
                probe.stdout.splitlines(),
                [
                    str(reused_env),
                    str(bundle / "downloads"),
                    str(bundle / "vendor" / "flaresolverr"),
                ],
            )

    def test_codex_config_fallback_replaces_existing_managed_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            config_path = home / ".codex" / "config.toml"
            _write_file(
                config_path,
                textwrap.dedent(
                    """
                    theme = "dark"

                    # BEGIN paper-fetch offline managed
                    [mcp_servers.paper-fetch]
                    command = "old-python"

                    [mcp_servers.paper-fetch.env]
                    PAPER_FETCH_ENV_FILE = "old.env"
                    # END paper-fetch offline managed

                    [profiles.default]
                    model = "gpt"
                    """
                ).lstrip(),
            )

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            config = config_path.read_text(encoding="utf-8")
            self.assertIn('theme = "dark"', config)
            self.assertIn("[profiles.default]", config)
            self.assertNotIn("old-python", config)
            self.assertNotIn("# BEGIN paper-fetch offline managed", config)
            self.assertEqual(config.count("# BEGIN paper-fetch installer managed"), 1)
            self.assertEqual(config.count("[mcp_servers.paper-fetch]"), 1)
            self.assertEqual(config.count("[mcp_servers.paper-fetch.env]"), 1)

    def test_uninstall_removes_user_level_integrations_without_deleting_bundle_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            cli_log = root / "cli.log"
            _write_recording_cli(fake_bin / "codex", cli_log)
            _write_recording_cli(fake_bin / "claude", cli_log)

            _write_file(bundle / "offline.env", 'ELSEVIER_API_KEY="secret"\n')
            _write_file(bundle / ".venv" / "bin" / "paper-fetch", "installed\n")
            _write_file(home / ".codex" / "skills" / "paper-fetch-skill" / "SKILL.md", "codex\n")
            _write_file(home / ".claude" / "skills" / "paper-fetch-skill" / "SKILL.md", "claude\n")
            managed = textwrap.dedent(
                """
                # BEGIN paper-fetch offline managed
                export PAPER_FETCH_ENV_FILE="/old/offline.env"
                # END paper-fetch offline managed
                """
            ).lstrip()
            _write_file(home / ".bashrc", f"keep bash before\n{managed}keep bash after\n")
            _write_file(home / ".zshrc", f"keep zsh before\n{managed}keep zsh after\n")
            _write_file(home / ".profile", f"keep profile before\n{managed}keep profile after\n")
            _write_file(home / ".config" / "fish" / "conf.d" / "paper-fetch-offline.fish", managed)
            _write_file(
                home / ".codex" / "config.toml",
                textwrap.dedent(
                    """
                    theme = "dark"

                    # BEGIN paper-fetch installer managed
                    [mcp_servers.paper-fetch]
                    command = "managed-python"

                    [mcp_servers.paper-fetch.env]
                    PAPER_FETCH_ENV_FILE = "managed.env"
                    # END paper-fetch installer managed

                    [mcp_servers.paper-fetch]
                    command = "fallback-python"

                    [mcp_servers.paper-fetch.env]
                    PAPER_FETCH_ENV_FILE = "fallback.env"

                    [profiles.default]
                    model = "gpt"
                    """
                ).lstrip(),
            )

            result = self._run_installer(bundle, fake_bin, home, "--uninstall")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(bundle.exists())
            self.assertEqual((bundle / "offline.env").read_text(encoding="utf-8"), 'ELSEVIER_API_KEY="secret"\n')
            self.assertTrue((bundle / ".venv" / "bin" / "paper-fetch").exists())
            self.assertFalse((home / ".codex" / "skills" / "paper-fetch-skill").exists())
            self.assertFalse((home / ".claude" / "skills" / "paper-fetch-skill").exists())

            self.assertEqual((home / ".bashrc").read_text(encoding="utf-8"), "keep bash before\nkeep bash after\n")
            self.assertEqual((home / ".zshrc").read_text(encoding="utf-8"), "keep zsh before\nkeep zsh after\n")
            self.assertEqual((home / ".profile").read_text(encoding="utf-8"), "keep profile before\nkeep profile after\n")
            self.assertFalse((home / ".config" / "fish" / "conf.d" / "paper-fetch-offline.fish").exists())

            config = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn('theme = "dark"', config)
            self.assertIn("[profiles.default]", config)
            self.assertNotIn("paper-fetch", config)
            self.assertNotIn("managed-python", config)
            self.assertNotIn("fallback-python", config)

            calls = [line.split("\t") for line in cli_log.read_text(encoding="utf-8").splitlines()]
            self.assertIn(["codex", "mcp", "remove", "paper-fetch"], calls)
            self.assertIn(["claude", "mcp", "remove", "-s", "user", "paper-fetch"], calls)
            self.assertFalse(any(call[:3] == ["codex", "mcp", "add"] for call in calls))
            self.assertFalse(any(call[:3] == ["claude", "mcp", "add"] for call in calls))
            self.assertIn("Bundle files were left in place", result.stdout)

    def test_uninstall_runs_without_bundle_assets_or_matching_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(
                Path(tmpdir),
                python_version="3.12.1",
                manifest_python_tag="cp313",
            )
            shutil.rmtree(bundle / "vendor")
            shutil.rmtree(bundle / "skills")
            (bundle / "sha256sums.txt").unlink()
            _write_file(
                home / ".bashrc",
                textwrap.dedent(
                    """
                    keep
                    # BEGIN paper-fetch offline managed
                    export PAPER_FETCH_ENV_FILE="/old/offline.env"
                    # END paper-fetch offline managed
                    """
                ).lstrip(),
            )

            result = self._run_installer(bundle, fake_bin, home, "--uninstall")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((home / ".bashrc").read_text(encoding="utf-8"), "keep\n")

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
            bashrc = (home / ".bashrc").read_text(encoding="utf-8")
            self.assertEqual(bashrc.count("# BEGIN paper-fetch offline managed"), 1)
            self.assertEqual(bashrc.count("# END paper-fetch offline managed"), 1)
            config = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertEqual(config.count("# BEGIN paper-fetch installer managed"), 1)
            self.assertEqual(config.count("[mcp_servers.paper-fetch]"), 1)
            self.assertEqual(config.count("[mcp_servers.paper-fetch.env]"), 1)

    def test_windows_installer_declares_abi_checksum_and_asset_guards(self) -> None:
        script = WINDOWS_INSTALLER_HELPER.read_text(encoding="utf-8")

        self.assertIn("formula-tools", script)
        self.assertIn("bin/texmath.exe", script)
        self.assertIn("ms-playwright", script)
        self.assertIn("runtime", script)
        self.assertIn("python.exe", script)
        self.assertIn("-X", script)
        self.assertIn("paper_fetch.mcp.server", script)

    def test_windows_installer_writes_managed_env_skills_and_path(self) -> None:
        script = WINDOWS_INSTALLER_HELPER.read_text(encoding="utf-8")

        self.assertIn("# BEGIN paper-fetch offline managed", script)
        self.assertIn("# END paper-fetch offline managed", script)
        self.assertIn("PAPER_FETCH_FORMULA_TOOLS_DIR", script)
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH", script)
        self.assertIn("FLARESOLVERR_SOURCE_DIR", script)
        self.assertIn(".codex", script)
        self.assertIn(".claude", script)
        self.assertIn("Add-UserPathEntry", script)
        self.assertNotIn(".cache/ms-playwright", script)

    def test_windows_installer_helper_preserves_existing_offline_env_user_values(self) -> None:
        script = WINDOWS_INSTALLER_HELPER.read_text(encoding="utf-8")

        self.assertIn("function Remove-ManagedEnvBlock", script)
        self.assertIn("if (Test-Path -LiteralPath $target -PathType Leaf)", script)
        self.assertIn("foreach ($line in (Remove-ManagedEnvBlock $existing))", script)
        self.assertIn("$lines.Add('ELSEVIER_API_KEY=\"\"')", script)
        self.assertIn("$lines.Add($OfflineManagedBegin)", script)
        self.assertIn("$lines.Add($OfflineManagedEnd)", script)

    def test_windows_installer_helper_registers_codex_and_claude_mcp(self) -> None:
        script = WINDOWS_INSTALLER_HELPER.read_text(encoding="utf-8")

        self.assertIn("codex", script)
        self.assertIn('"mcp", "remove", $McpName', script)
        self.assertIn('"mcp", "add"', script)
        self.assertIn("Write-CodexConfigToml", script)
        self.assertIn("[mcp_servers.paper-fetch]", script)
        self.assertIn("[mcp_servers.paper-fetch.env]", script)
        self.assertIn("claude", script)
        self.assertIn('"mcp", "add", "-s", "user"', script)
        self.assertIn("PYTHONUTF8", script)
        self.assertIn("PYTHONIOENCODING", script)

    def test_windows_installer_smoke_checks_do_not_use_user_playwright_cache(self) -> None:
        script = WINDOWS_INSTALLER_HELPER.read_text(encoding="utf-8")

        self.assertIn("provider_status_payload", script)
        self.assertIn("manager.chromium.executable_path", script)
        self.assertIn("assert root in executable.parents", script)
        self.assertIn("paper_fetch.mcp.tools", script)

    def test_windows_uninstaller_removes_managed_skills_path_and_mcp(self) -> None:
        script = WINDOWS_INSTALLER_HELPER.read_text(encoding="utf-8")

        self.assertIn('"Uninstall"', script)
        self.assertIn("Remove-Skills", script)
        self.assertIn("Remove-UserPathEntry", script)
        self.assertIn("Unregister-CodexMcp", script)
        self.assertIn("Unregister-ClaudeMcp", script)
        self.assertIn("Remove-CodexConfigToml", script)


if __name__ == "__main__":
    unittest.main()
