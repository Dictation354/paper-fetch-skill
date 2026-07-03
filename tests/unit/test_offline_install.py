from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest

from ._installer_support import write_executable as _write_executable


REPO_ROOT = Path(__file__).resolve().parents[2]
LINUX_INSTALLER = REPO_ROOT / "install-offline.sh"
WINDOWS_INSTALLER = REPO_ROOT / "install-offline.ps1"
WINDOWS_INSTALLER_HELPER = REPO_ROOT / "scripts" / "windows-installer-helper.ps1"
LINUX_OFFLINE_BUILD = REPO_ROOT / "scripts" / "build-offline-package.sh"
WINDOWS_OFFLINE_BUILD = REPO_ROOT / "scripts" / "build-offline-package-windows.ps1"
WINDOWS_INNO_INSTALLER = REPO_ROOT / "installer" / "paper-fetch-skill.iss"


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
    real_python = shlex.quote(sys.executable)
    return f"""\
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION="{version}"
    TAG="{tag}"
    REAL_PYTHON={real_python}

    while [[ "${{1:-}}" == "-X" ]]; do
      shift 2
    done

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
      if [[ "$code" == *'sys.argv[2].split'* ]]; then
        manifest="${{3:-}}"
        key="${{4:-}}"
        if [[ -f "$manifest" ]]; then
          case "$key" in
            target.platform)
              grep -oE '"platform"[[:space:]]*:[[:space:]]*"[^"]+"' "$manifest" | head -n 1 | sed -E 's/.*"platform"[[:space:]]*:[[:space:]]*"([^"]+)".*/\\1/'
              ;;
            target.arch)
              grep -oE '"arch"[[:space:]]*:[[:space:]]*"[^"]+"' "$manifest" | head -n 1 | sed -E 's/.*"arch"[[:space:]]*:[[:space:]]*"([^"]+)".*/\\1/'
              ;;
          esac
        fi
        exit 0
      fi
      if [[ "$code" == *'installer_manifest_values'* ]]; then
        cat <<'OUT'
    installer_manifest_values
    # BEGIN paper-fetch offline managed
    # END paper-fetch offline managed
    # BEGIN paper-fetch installer managed
    # END paper-fetch installer managed
    paper-fetch-skill
    paper-fetch
    [mcp.env_keys]
    PYTHONUTF8
    PYTHONIOENCODING
    PAPER_FETCH_ENV_FILE
    PAPER_FETCH_DOWNLOAD_DIR
    PAPER_FETCH_FORMULA_TOOLS_DIR
    PAPER_FETCH_IMAGE_TOOLS_DIR
    MATHML_TO_LATEX_NODE_BIN
    CLOAKBROWSER_HEADLESS
    [env_sets.offline_env_keys]
    PAPER_FETCH_DOWNLOAD_DIR
    PAPER_FETCH_FORMULA_TOOLS_DIR
    PAPER_FETCH_IMAGE_TOOLS_DIR
    MATHML_TO_LATEX_NODE_BIN
    CLOAKBROWSER_HEADLESS
    PYTHONUTF8
    PYTHONIOENCODING
    PAPER_FETCH_BROWSER_USER_AGENT
    [env_sets.shell_env_keys]
    PAPER_FETCH_ENV_FILE
    PAPER_FETCH_DOWNLOAD_DIR
    PAPER_FETCH_FORMULA_TOOLS_DIR
    PAPER_FETCH_IMAGE_TOOLS_DIR
    MATHML_TO_LATEX_NODE_BIN
    CLOAKBROWSER_HEADLESS
    PYTHONUTF8
    PYTHONIOENCODING
    [env_sets.activate_env_keys]
    PAPER_FETCH_ENV_FILE
    PAPER_FETCH_DOWNLOAD_DIR
    PAPER_FETCH_FORMULA_TOOLS_DIR
    PAPER_FETCH_IMAGE_TOOLS_DIR
    MATHML_TO_LATEX_NODE_BIN
    CLOAKBROWSER_HEADLESS
    PYTHONUTF8
    PYTHONIOENCODING
    OUT
        exit 0
      fi
      if [[ "$code" == *'cloakbrowser'* ]]; then
        exit 0
      fi
      exit 0
    fi

    if [[ "${{1:-}}" == "-" ]]; then
      code="$(cat)"
      "$REAL_PYTHON" "$@" <<< "$code"
      exit $?
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


def _fake_uname_script(kernel: str, machine: str) -> str:
    return f"""\
    #!/usr/bin/env bash
    case "${{1:-}}" in
      -s) echo "{kernel}" ;;
      -m) echo "{machine}" ;;
      *) echo "{kernel}" ;;
    esac
    """


def _write_checksums(root: Path) -> None:
    lines: list[str] = []
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and item.name != "sha256sums.txt"
    ):
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
        target_platform: str = "linux",
        target_arch: str = "x86_64",
        uname_kernel: str = "Linux",
        uname_machine: str = "x86_64",
    ) -> tuple[Path, Path, Path]:
        bundle = root / "bundle"
        bundle.mkdir()
        shutil.copy2(REPO_ROOT / "install-offline.sh", bundle / "install-offline.sh")
        (bundle / "install-offline.sh").chmod(0o755)
        shutil.copytree(REPO_ROOT / "installer", bundle / "installer")

        manifest_python_tag = manifest_python_tag or _python_tag(python_version)
        _write_file(
            bundle / "offline-manifest.json",
            (
                '{"target": {'
                f'"platform": "{target_platform}", '
                f'"arch": "{target_arch}", '
                f'"python_tag": "{manifest_python_tag}"'
                "}}\n"
            ),
        )
        _write_file(bundle / ".env.example", 'ELSEVIER_API_KEY=""\n')
        _write_file(
            bundle / "runtime" / "site-packages" / "paper_fetch" / "__init__.py", "\n"
        )
        _write_file(
            bundle / "runtime" / "site-packages" / "cloakbrowser" / "__init__.py", "\n"
        )
        _write_executable(
            bundle / "runtime" / "site-packages" / "playwright" / "driver" / "node",
            "#!/usr/bin/env bash\nexit 0\n",
        )
        _write_executable(
            bundle / "runtime" / "paper-fetch-python",
            _fake_python_script(python_version),
        )
        _write_executable(
            bundle / "bin" / "paper-fetch",
            '#!/usr/bin/env bash\nif [[ "${1:-}" == "--help" ]]; then exit 0; fi\nexit 0\n',
        )
        _write_executable(
            bundle / "bin" / "paper-fetch-mcp", "#!/usr/bin/env bash\nexit 0\n"
        )
        _write_executable(
            bundle / "bin" / "paper-fetch-install-formula-tools",
            "#!/usr/bin/env bash\nexit 0\n",
        )
        _write_executable(
            bundle / "bin" / "paper-fetch-install-image-tools",
            "#!/usr/bin/env bash\nexit 0\n",
        )
        _write_file(
            bundle / "skills" / "paper-fetch-skill" / "SKILL.md",
            "# Paper fetch skill\n",
        )
        _write_file(
            bundle / "skills" / "paper-fetch-skill" / "references" / "tool-contract.md",
            "Tool contract\n",
        )
        _write_executable(
            bundle / "formula-tools" / "bin" / "texmath",
            "#!/usr/bin/env bash\nexit 0\n",
        )
        (bundle / "image-tools" / "bin").mkdir(parents=True, exist_ok=True)

        fake_bin = root / "fake-bin"
        _write_executable(fake_bin / "python3", _fake_python_script(python_version))
        _write_executable(
            fake_bin / "uname", _fake_uname_script(uname_kernel, uname_machine)
        )

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
        install_dir: Path | None = None,
        use_default_install_dir: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["PATH"] = f"{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin"
        env["PAPER_FETCH_OFFLINE_PYTHON_BIN"] = str(fake_bin / "python3")
        if shell is None:
            env.pop("SHELL", None)
        else:
            env["SHELL"] = shell
        if extra_env:
            env.update(extra_env)
        command = [str(bundle / "install-offline.sh"), "--skip-smoke"]
        if not use_default_install_dir:
            command.extend(["--install-dir", str(install_dir or bundle)])
        command.extend(args)
        return subprocess.run(
            command,
            cwd=bundle,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_default_install_writes_cdp_browser_env_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            user_env = home / ".config" / "paper-fetch" / ".env"
            _write_file(user_env, 'ELSEVIER_API_KEY="secret"\n')

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                user_env.read_text(encoding="utf-8"), 'ELSEVIER_API_KEY="secret"\n'
            )
            offline_env = (bundle / "offline.env").read_text(encoding="utf-8")
            self.assertIn(
                'PAPER_FETCH_BROWSER_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                offline_env,
            )
            self.assertNotIn("# PAPER_FETCH_BROWSER_USER_AGENT", offline_env)
            self.assertIn(
                'CLOAKBROWSER_CDP_ENDPOINT="ws://127.0.0.1:9222/devtools/browser/..."',
                offline_env,
            )
            self.assertIn('CLOAKBROWSER_HEADLESS="true"', offline_env)
            self.assertIn(
                'CLOAKBROWSER_BINARY_PATH="/absolute/path/to/chrome"', offline_env
            )
            self.assertIn(
                f'PAPER_FETCH_IMAGE_TOOLS_DIR="{bundle / "image-tools"}"', offline_env
            )
            self.assertIn(
                f'MATHML_TO_LATEX_NODE_BIN="{bundle / "runtime" / "site-packages" / "playwright" / "driver" / "node"}"',
                offline_env,
            )
            self.assertIn('PYTHONUTF8="1"', offline_env)
            self.assertIn('PYTHONIOENCODING="utf-8"', offline_env)
            self.assertNotIn("PLAYWRIGHT_BROWSERS_PATH", offline_env)
            self.assertEqual(
                (bundle / "runtime" / "python-bin").read_text(encoding="utf-8"),
                f"{fake_bin / 'python3'}\n",
            )
            self.assertIn("CloakBrowser headless: true", result.stdout)
            self.assertIn(
                "Browser-backed providers auto-start cloakbrowser Chrome", result.stdout
            )

    def test_default_install_copies_runtime_to_user_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            install_root = home / ".local" / "share" / "paper-fetch-skill"

            result = self._run_installer(
                bundle, fake_bin, home, use_default_install_dir=True
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (
                    install_root
                    / "runtime"
                    / "site-packages"
                    / "paper_fetch"
                    / "__init__.py"
                ).exists()
            )
            self.assertTrue((install_root / "bin" / "paper-fetch").exists())
            self.assertTrue((install_root / "runtime" / "paper-fetch-python").exists())
            self.assertFalse((install_root / "bin" / "python").exists())
            self.assertTrue((install_root / "install-offline.sh").exists())
            self.assertTrue((install_root / "activate-offline.sh").exists())
            self.assertTrue((install_root / "offline.env").exists())
            bashrc = (home / ".bashrc").read_text(encoding="utf-8")
            self.assertIn(
                f'export PAPER_FETCH_ENV_FILE="{install_root / "offline.env"}"', bashrc
            )
            self.assertIn(f"{install_root / 'bin'}", bashrc)
            self.assertIn(f"{install_root / 'image-tools' / 'bin'}", bashrc)
            self.assertIn(
                f'export PAPER_FETCH_IMAGE_TOOLS_DIR="{install_root / "image-tools"}"',
                bashrc,
            )
            self.assertFalse((bundle / "offline.env").exists())
            self.assertIn(f"Install directory: {install_root}", result.stdout)

    def test_install_dir_upgrade_cleans_old_payload_and_preserves_offline_env(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            install_root = root / "fixed-install"
            for stale in ("src", "tests", "wheelhouse", "dist", ".github"):
                _write_file(install_root / stale / "old.txt", "old\n")
            _write_file(install_root / "pyproject.toml", "[project]\n")
            _write_file(
                install_root / "offline.env",
                textwrap.dedent(
                    """
                    ELSEVIER_API_KEY="secret"
                    USER_NOTE="keep"

                    # BEGIN paper-fetch offline managed
                    PAPER_FETCH_DOWNLOAD_DIR="/old/downloads"
                    # END paper-fetch offline managed
                    """
                ).lstrip(),
            )

            result = self._run_installer(
                bundle, fake_bin, home, install_dir=install_root
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            for stale in (
                "src",
                "tests",
                "wheelhouse",
                "dist",
                ".github",
                "pyproject.toml",
            ):
                self.assertFalse((install_root / stale).exists(), stale)
            self.assertTrue(
                (
                    install_root
                    / "runtime"
                    / "site-packages"
                    / "paper_fetch"
                    / "__init__.py"
                ).exists()
            )
            offline_env = (install_root / "offline.env").read_text(encoding="utf-8")
            self.assertIn('ELSEVIER_API_KEY="secret"', offline_env)
            self.assertIn('USER_NOTE="keep"', offline_env)
            self.assertNotIn("/old/downloads", offline_env)
            self.assertIn(
                f'PAPER_FETCH_DOWNLOAD_DIR="{install_root / "downloads"}"', offline_env
            )
            self.assertIn(
                f'PAPER_FETCH_IMAGE_TOOLS_DIR="{install_root / "image-tools"}"',
                offline_env,
            )

    def test_shell_startup_blocks_set_headless_without_legacy_browser_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            bash_result = self._run_installer(bundle, fake_bin, home, shell="/bin/bash")
            fish_result = self._run_installer(
                bundle, fake_bin, home, shell="/usr/bin/fish"
            )

            self.assertEqual(bash_result.returncode, 0, bash_result.stderr)
            self.assertEqual(fish_result.returncode, 0, fish_result.stderr)
            bashrc = (home / ".bashrc").read_text(encoding="utf-8")
            fish_config = (
                home / ".config" / "fish" / "conf.d" / "paper-fetch-offline.fish"
            ).read_text(encoding="utf-8")
            self.assertIn(
                f'export PAPER_FETCH_ENV_FILE="{bundle / "offline.env"}"', bashrc
            )
            self.assertIn(
                f'set -gx PAPER_FETCH_ENV_FILE "{bundle / "offline.env"}"', fish_config
            )
            self.assertIn(
                f'export PAPER_FETCH_IMAGE_TOOLS_DIR="{bundle / "image-tools"}"', bashrc
            )
            self.assertIn(
                f'set -gx PAPER_FETCH_IMAGE_TOOLS_DIR "{bundle / "image-tools"}"',
                fish_config,
            )
            self.assertIn('export CLOAKBROWSER_HEADLESS="true"', bashrc)
            self.assertIn('set -gx CLOAKBROWSER_HEADLESS "true"', fish_config)
            self.assertIn("export MATHML_TO_LATEX_NODE_BIN=", bashrc)
            self.assertIn("set -gx MATHML_TO_LATEX_NODE_BIN ", fish_config)
            self.assertIn('export PYTHONUTF8="1"', bashrc)
            self.assertIn('set -gx PYTHONUTF8 "1"', fish_config)
            self.assertIn('export PYTHONIOENCODING="utf-8"', bashrc)
            self.assertIn('set -gx PYTHONIOENCODING "utf-8"', fish_config)
            self.assertNotIn("PLAYWRIGHT_BROWSERS_PATH", bashrc + fish_config)

    def test_unknown_preset_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home, "--preset=desktop")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--preset must be headless or headful", result.stderr)

    def test_macos_bundle_headful_preset_sets_headless_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(
                Path(tmpdir),
                target_platform="macos",
                target_arch="arm64",
                uname_kernel="Darwin",
                uname_machine="arm64",
            )

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--preset=headful",
                extra_env={"DISPLAY": "", "WAYLAND_DISPLAY": ""},
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            offline_env = (bundle / "offline.env").read_text(encoding="utf-8")
            self.assertIn("CLOAKBROWSER_CDP_ENDPOINT", offline_env)
            self.assertIn('CLOAKBROWSER_HEADLESS="false"', offline_env)
            self.assertIn("CloakBrowser headless: false", result.stdout)

    def test_cli_registration_uses_offline_env_with_headless_without_legacy_browser_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            cli_log = root / "cli.log"
            _write_recording_cli(fake_bin / "codex", cli_log)
            _write_recording_cli(fake_bin / "claude", cli_log)

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = [
                line.split("\t")
                for line in cli_log.read_text(encoding="utf-8").splitlines()
            ]
            codex_add = next(
                call for call in calls if call[:3] == ["codex", "mcp", "add"]
            )
            self.assertIn(f"PAPER_FETCH_ENV_FILE={bundle / 'offline.env'}", codex_add)
            self.assertIn(
                f"MATHML_TO_LATEX_NODE_BIN={bundle / 'runtime' / 'site-packages' / 'playwright' / 'driver' / 'node'}",
                codex_add,
            )
            self.assertIn(
                f"PAPER_FETCH_IMAGE_TOOLS_DIR={bundle / 'image-tools'}", codex_add
            )
            self.assertIn("CLOAKBROWSER_HEADLESS=true", codex_add)
            self.assertFalse(
                any(arg.startswith("CLOAKBROWSER_BINARY_PATH=") for arg in codex_add)
            )
            self.assertFalse(
                any("PLAYWRIGHT_BROWSERS_PATH" in arg for arg in codex_add)
            )
            claude_add = next(
                call for call in calls if call[:3] == ["claude", "mcp", "add"]
            )
            self.assertIn("-s", claude_add)
            self.assertIn("user", claude_add)
            self.assertIn("--", claude_add)
            self.assertLess(claude_add.index("--"), claude_add.index("paper-fetch"))
            self.assertIn(f"PAPER_FETCH_ENV_FILE={bundle / 'offline.env'}", claude_add)
            self.assertIn(
                f"PAPER_FETCH_IMAGE_TOOLS_DIR={bundle / 'image-tools'}", claude_add
            )

    def test_missing_codex_cli_writes_config_toml_with_headless_without_browser_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            config = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
            self.assertIn("# BEGIN paper-fetch installer managed", config)
            self.assertIn("[mcp_servers.paper-fetch]", config)
            self.assertIn(f'PAPER_FETCH_ENV_FILE = "{bundle / "offline.env"}"', config)
            self.assertIn('MATHML_TO_LATEX_NODE_BIN = "', config)
            self.assertIn(
                f'PAPER_FETCH_IMAGE_TOOLS_DIR = "{bundle / "image-tools"}"', config
            )
            self.assertIn('CLOAKBROWSER_HEADLESS = "true"', config)
            self.assertNotIn("CLOAKBROWSER_BINARY_PATH", config)
            self.assertNotIn("PLAYWRIGHT_BROWSERS_PATH", config)

    def test_antigravity_mcp_config_uses_manifest_env_keys_and_preserves_existing_servers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            antigravity_home = home / ".gemini" / "antigravity-cli"
            _write_file(
                antigravity_home / "mcp_config.json",
                json.dumps({"mcpServers": {"keep-server": {"command": "keep"}}}),
            )

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (
                    antigravity_home / "skills" / "paper-fetch-skill" / "SKILL.md"
                ).exists()
            )
            data = json.loads(
                (antigravity_home / "mcp_config.json").read_text(encoding="utf-8")
            )
            servers = data["mcpServers"]
            self.assertIn("keep-server", servers)
            entry = servers["paper-fetch"]
            self.assertEqual(
                entry["command"], str(bundle / "runtime" / "paper-fetch-python")
            )
            self.assertEqual(
                entry["args"], ["-X", "utf8", "-m", "paper_fetch.mcp.server"]
            )
            manifest = json.loads(
                (REPO_ROOT / "installer" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(set(entry["env"]), set(manifest["mcp"]["env_keys"]))
            self.assertEqual(entry["env"]["PYTHONUTF8"], "1")
            self.assertEqual(entry["env"]["PYTHONIOENCODING"], "utf-8")
            self.assertEqual(
                entry["env"]["PAPER_FETCH_ENV_FILE"], str(bundle / "offline.env")
            )
            self.assertEqual(
                entry["env"]["PAPER_FETCH_IMAGE_TOOLS_DIR"],
                str(bundle / "image-tools"),
            )
            self.assertEqual(
                entry["env"]["MATHML_TO_LATEX_NODE_BIN"],
                str(
                    bundle
                    / "runtime"
                    / "site-packages"
                    / "playwright"
                    / "driver"
                    / "node"
                ),
            )

    def test_reuse_env_file_keeps_file_untouched_and_activate_script_sets_runtime_dirs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            reused_env = root / "shared" / "offline.env"
            marker = root / "activate-command-ran"
            sentinel = f"$(touch {marker})"
            reused_payload = (
                'ELSEVIER_API_KEY="secret"\n'
                f'PAPER_FETCH_ACTIVATE_SENTINEL="{sentinel}"\n'
            )
            _write_file(reused_env, reused_payload)

            result = self._run_installer(
                bundle, fake_bin, home, "--reuse-env-file", str(reused_env)
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(reused_env.read_text(encoding="utf-8"), reused_payload)
            self.assertFalse((bundle / "offline.env").exists())

            probe = subprocess.run(
                [
                    "bash",
                    "-lc",
                    (
                        f'source "{bundle / "activate-offline.sh"}"; '
                        'printf "%s\\n%s\\n%s\\n%s\\n%s\\n%s\\n%s\\n" '
                        '"$PAPER_FETCH_ENV_FILE" '
                        '"$PAPER_FETCH_DOWNLOAD_DIR" '
                        '"$PAPER_FETCH_IMAGE_TOOLS_DIR" '
                        '"$MATHML_TO_LATEX_NODE_BIN" '
                        '"$PYTHONUTF8" '
                        '"$PYTHONIOENCODING" '
                        '"$PAPER_FETCH_ACTIVATE_SENTINEL"'
                    ),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual(
                probe.stdout.splitlines(),
                [
                    str(reused_env),
                    str(bundle / "downloads"),
                    str(bundle / "image-tools"),
                    str(
                        bundle
                        / "runtime"
                        / "site-packages"
                        / "playwright"
                        / "driver"
                        / "node"
                    ),
                    "1",
                    "utf-8",
                    sentinel,
                ],
            )

            zsh = shutil.which("zsh")
            if zsh:
                zsh_probe = subprocess.run(
                    [
                        zsh,
                        "-lc",
                        (
                            f'source "{bundle / "activate-offline.sh"}"; '
                            'printf "%s\\n%s\\n%s\\n%s\\n%s\\n%s\\n%s\\n" '
                            '"$PAPER_FETCH_ENV_FILE" '
                            '"$PAPER_FETCH_DOWNLOAD_DIR" '
                            '"$PAPER_FETCH_IMAGE_TOOLS_DIR" '
                            '"$MATHML_TO_LATEX_NODE_BIN" '
                            '"$PYTHONUTF8" '
                            '"$PYTHONIOENCODING" '
                            '"$PAPER_FETCH_ACTIVATE_SENTINEL"'
                        ),
                    ],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(zsh_probe.returncode, 0, zsh_probe.stderr)
                self.assertEqual(
                    zsh_probe.stdout.splitlines(),
                    [
                        str(reused_env),
                        str(bundle / "downloads"),
                        str(bundle / "image-tools"),
                        str(
                            bundle
                            / "runtime"
                            / "site-packages"
                            / "playwright"
                            / "driver"
                            / "node"
                        ),
                        "1",
                        "utf-8",
                        sentinel,
                    ],
                )

    def test_activate_script_parses_dotenv_without_executing_shell_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            marker = root / "default-activate-command-ran"
            sentinel = f"$(touch {marker})"

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            offline_env = bundle / "offline.env"
            offline_env.write_text(
                offline_env.read_text(encoding="utf-8")
                + "\n"
                + 'export PAPER_FETCH_SPACED="hello world"\n'
                + f'PAPER_FETCH_ACTIVATE_SENTINEL="{sentinel}"\n',
                encoding="utf-8",
            )

            probe = subprocess.run(
                [
                    "bash",
                    "-lc",
                    (
                        f'source "{bundle / "activate-offline.sh"}"; '
                        'printf "%s\\n%s\\n%s\\n%s\\n%s\\n" '
                        '"$PAPER_FETCH_SPACED" '
                        '"$PAPER_FETCH_ACTIVATE_SENTINEL" '
                        '"$MATHML_TO_LATEX_NODE_BIN" '
                        '"$PYTHONUTF8" '
                        '"$PYTHONIOENCODING"'
                    ),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual(
                probe.stdout.splitlines(),
                [
                    "hello world",
                    sentinel,
                    str(
                        bundle
                        / "runtime"
                        / "site-packages"
                        / "playwright"
                        / "driver"
                        / "node"
                    ),
                    "1",
                    "utf-8",
                ],
            )

    def test_activate_script_is_sourceable_from_macos_default_zsh(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            activate_script = (bundle / "activate-offline.sh").read_text(
                encoding="utf-8"
            )
            self.assertIn("${BASH_SOURCE:-}", activate_script)
            self.assertIn("${ZSH_VERSION:-}", activate_script)
            self.assertIn("${(%):-%x}", activate_script)

            zsh = shutil.which("zsh")
            if not zsh:
                self.skipTest("zsh is not installed in this test environment")
            probe = subprocess.run(
                [
                    zsh,
                    "-lc",
                    (
                        f'source "{bundle / "activate-offline.sh"}"; '
                        'printf "%s\\n%s\\n%s\\n" '
                        '"$PAPER_FETCH_ENV_FILE" "$PAPER_FETCH_DOWNLOAD_DIR" "$PAPER_FETCH_IMAGE_TOOLS_DIR"'
                    ),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertEqual(
                probe.stdout.splitlines(),
                [
                    str(bundle / "offline.env"),
                    str(bundle / "downloads"),
                    str(bundle / "image-tools"),
                ],
            )

    def test_uninstall_removes_user_level_integrations_without_deleting_bundle_data(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            cli_log = root / "cli.log"
            _write_recording_cli(fake_bin / "codex", cli_log)
            _write_recording_cli(fake_bin / "claude", cli_log)

            _write_file(bundle / "offline.env", 'ELSEVIER_API_KEY="secret"\n')
            _write_file(bundle / "bin" / "paper-fetch", "installed\n")
            _write_file(
                home / ".codex" / "skills" / "paper-fetch-skill" / "SKILL.md", "codex\n"
            )
            _write_file(
                home
                / ".gemini"
                / "antigravity-cli"
                / "skills"
                / "paper-fetch-skill"
                / "SKILL.md",
                "antigravity\n",
            )
            _write_file(
                home / ".gemini" / "antigravity-cli" / "mcp_config.json",
                json.dumps(
                    {
                        "mcpServers": {
                            "keep-server": {"command": "keep"},
                            "paper-fetch": {"command": "old", "args": []},
                        }
                    }
                )
                + "\n",
            )
            managed = textwrap.dedent(
                """
                # BEGIN paper-fetch offline managed
                export PAPER_FETCH_ENV_FILE="/old/offline.env"
                # END paper-fetch offline managed
                """
            ).lstrip()
            _write_file(
                home / ".bashrc", f"keep bash before\n{managed}keep bash after\n"
            )

            result = self._run_installer(bundle, fake_bin, home, "--uninstall")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(bundle.exists())
            self.assertEqual(
                (bundle / "offline.env").read_text(encoding="utf-8"),
                'ELSEVIER_API_KEY="secret"\n',
            )
            self.assertFalse(
                (home / ".codex" / "skills" / "paper-fetch-skill").exists()
            )
            self.assertFalse(
                (
                    home
                    / ".gemini"
                    / "antigravity-cli"
                    / "skills"
                    / "paper-fetch-skill"
                ).exists()
            )
            antigravity_config = json.loads(
                (home / ".gemini" / "antigravity-cli" / "mcp_config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("keep-server", antigravity_config["mcpServers"])
            self.assertNotIn("paper-fetch", antigravity_config["mcpServers"])
            self.assertEqual(
                (home / ".bashrc").read_text(encoding="utf-8"),
                "keep bash before\nkeep bash after\n",
            )
            calls = [
                line.split("\t")
                for line in cli_log.read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn(["codex", "mcp", "remove", "paper-fetch"], calls)
            self.assertFalse(any(call[:3] == ["codex", "mcp", "add"] for call in calls))
            self.assertIn("Install directory was left in place", result.stdout)

    def test_purge_removes_install_directory_after_user_level_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            install_root = root / "installed"
            result = self._run_installer(
                bundle, fake_bin, home, install_dir=install_root
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(install_root.exists())

            purge = self._run_installer(
                bundle, fake_bin, home, "--purge", install_dir=install_root
            )

            self.assertEqual(purge.returncode, 0, purge.stderr)
            self.assertFalse(install_root.exists())
            self.assertIn("Install directory deleted", purge.stdout)

    def test_matching_manifest_and_interpreter_tags_are_accepted(self) -> None:
        for python_version, python_tag in (
            ("3.11.9", "cp311"),
            ("3.12.7", "cp312"),
            ("3.13.3", "cp313"),
        ):
            with (
                self.subTest(python_tag=python_tag),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
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

    def test_installers_do_not_call_playwright_browser_install(self) -> None:
        linux_script = LINUX_INSTALLER.read_text(encoding="utf-8")
        windows_script = WINDOWS_INSTALLER.read_text(encoding="utf-8")

        combined = linux_script + windows_script
        self.assertNotIn("python -m playwright install chromium", combined)
        self.assertNotIn("-m playwright install chromium", combined)
        self.assertNotIn("cloakbrowser.ensure_runtime()", combined)
        self.assertNotIn('assert hasattr(cloakbrowser, "launch")', combined)
        self.assertIn(
            "from paper_fetch.runtime_browser import BrowserContextManager", combined
        )

    def test_windows_installer_helper_uses_cdp_browser_runtime_smoke(self) -> None:
        script = WINDOWS_INSTALLER_HELPER.read_text(encoding="utf-8")

        self.assertNotIn("[switch]$ProbeLaunch", script)
        self.assertIn("[string]$LogPath", script)
        self.assertIn("Invoke-InstallerStep", script)
        self.assertIn('Invoke-InstallerStep -Name "smoke checks"', script)
        self.assertIn("non-critical warning", script)
        self.assertIn("exit 2", script)
        self.assertIn("exit 0", script)
        self.assertIn("function Invoke-RuntimePythonScript", script)
        self.assertIn("[System.IO.Path]::GetTempPath()", script)
        self.assertIn("[System.Guid]::NewGuid()", script)
        self.assertIn(
            "Remove-Item -LiteralPath $scriptPath -Force -ErrorAction SilentlyContinue",
            script,
        )
        self.assertIn("Invoke-RuntimePythonScript -Script @'", script)
        self.assertIn("Invoke-RuntimePythonScript -Script $browserRuntimeCheck", script)
        self.assertIn("import cloakbrowser", script)
        self.assertIn("import playwright", script)
        self.assertIn(
            "from paper_fetch.runtime_browser import BrowserContextManager", script
        )
        self.assertIn('assert hasattr(cloakbrowser, "ensure_binary")', script)
        self.assertNotIn('assert hasattr(cloakbrowser, "launch")', script)
        self.assertIn("function Get-BrowserUserAgent", script)
        self.assertIn(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            script,
        )
        self.assertNotIn("# PAPER_FETCH_BROWSER_USER_AGENT", script)
        self.assertIn("$OfflineEnvKeys = @(", script)
        self.assertIn("env_sets.offline_env_keys", script)
        self.assertIn("Format-DotenvAssignment", script)
        self.assertIn("CLOAKBROWSER_CDP_ENDPOINT", script)
        self.assertIn("# CLOAKBROWSER_BINARY_PATH", script)
        self.assertNotIn('os.environ.get("CLOAKBROWSER_BINARY_PATH")', script)
        self.assertNotIn("probe-launch", script)
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", script)
        self.assertIn("PAPER_FETCH_IMAGE_TOOLS_DIR", script)
        self.assertIn("playwright/driver/node.exe", script)
        self.assertIn('CLOAKBROWSER_HEADLESS = "true"', script)
        self.assertIn("CLOAKBROWSER_HEADLESS", script)
        self.assertIn('@("--version")', script)
        self.assertIn(
            '$args += @("--", $McpName, $python, "-X", "utf8", "-m", "paper_fetch.mcp.server")',
            script,
        )
        self.assertIn('$args = @("mcp", "add", "-s", "user")', script)
        self.assertIn('"remove", "-s", "user"', script)
        self.assertNotIn('"-X", "utf8", "-c"', script)
        self.assertNotIn("sessions.list", script)
        self.assertNotIn("playwright.sync_api", script)

    def test_windows_offline_installer_declares_cdp_env_hint_without_playwright_runtime_path(
        self,
    ) -> None:
        script = WINDOWS_INSTALLER.read_text(encoding="utf-8")

        self.assertIn("Repo-local legacy Windows offline installer", script)
        self.assertIn("CLOAKBROWSER_CDP_ENDPOINT", script)
        self.assertIn('"CLOAKBROWSER_HEADLESS"', script)
        self.assertIn('$env:CLOAKBROWSER_HEADLESS = "true"', script)
        self.assertIn('$env:PYTHONUTF8 = "1"', script)
        self.assertIn('$env:PYTHONIOENCODING = "utf-8"', script)
        self.assertIn("env_sets.offline_env_keys", script)
        self.assertIn("Format-DotenvAssignment", script)
        self.assertIn("# CLOAKBROWSER_BINARY_PATH", script)
        self.assertNotIn("CLOAKBROWSER_BINARY_PATH is set", script)
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", script)
        self.assertIn("PAPER_FETCH_IMAGE_TOOLS_DIR", script)
        self.assertIn("playwright/driver/node.exe", script)
        self.assertIn("bundled node.exe --version failed", script)
        self.assertIn("Test-BrowserRuntimePackage", script)
        self.assertNotIn("PLAYWRIGHT_BROWSERS_PATH =", script)

    def test_windows_inno_installer_cleans_old_payload_and_restores_offline_env_before_helper(
        self,
    ) -> None:
        script = WINDOWS_INNO_INSTALLER.read_text(encoding="utf-8")

        self.assertIn("BackupOfflineEnv", script)
        self.assertIn("RunOldUninstaller", script)
        self.assertIn("CleanOldInstallDirectory", script)
        self.assertIn("RestoreOfflineEnv", script)
        self.assertIn("QuietUninstallString", script)
        self.assertIn("UninstallString", script)
        self.assertIn("/VERYSILENT /SUPPRESSMSGBOXES /NORESTART", script)
        self.assertIn("DelTree(AppDir, True, True, True)", script)
        self.assertIn("CurStep = ssInstall", script)
        self.assertIn("CurStep = ssPostInstall", script)
        self.assertIn("RunPostInstallHelper", script)
        self.assertIn(
            "HelperPath := ExpandConstant('{app}\\scripts\\windows-installer-helper.ps1')",
            script,
        )
        self.assertIn("PostInstallHelperWarning := True", script)
        self.assertIn("install-helper.log", script)
        self.assertIn('-LogPath "', script)
        self.assertIn('" -Action Install', script)
        self.assertIn("RestoreOfflineEnv;\n    RunPostInstallHelper;", script)
        self.assertNotIn(
            "Paper Fetch Skill post-install helper failed with exit code", script
        )

    def test_installer_manifest_declares_runtime_env_for_mcp_registration(self) -> None:
        manifest = json.loads(
            (REPO_ROOT / "installer" / "manifest.json").read_text(encoding="utf-8")
        )

        mcp_env_keys = manifest["mcp"]["env_keys"]
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", mcp_env_keys)
        self.assertIn("PAPER_FETCH_IMAGE_TOOLS_DIR", mcp_env_keys)
        self.assertEqual(
            set(manifest["env_sets"]["shell_env_keys"]),
            set(mcp_env_keys),
        )
        self.assertEqual(
            set(manifest["env_sets"]["activate_env_keys"]),
            set(mcp_env_keys),
        )
        self.assertEqual(
            set(manifest["env_sets"]["offline_env_keys"]),
            (set(mcp_env_keys) - {"PAPER_FETCH_ENV_FILE"})
            | {"PAPER_FETCH_BROWSER_USER_AGENT"},
        )

    def test_windows_offline_build_writes_default_mathml_node_env(self) -> None:
        script = WINDOWS_OFFLINE_BUILD.read_text(encoding="utf-8")

        self.assertIn("MATHML_TO_LATEX_NODE_BIN", script)
        self.assertIn("PAPER_FETCH_IMAGE_TOOLS_DIR", script)
        self.assertIn("--offline-bundle", script)
        self.assertIn("--repo-root", script)
        self.assertIn("runtime/Lib/site-packages/playwright/driver/node.exe", script)
        self.assertIn("do not rely on a bare `node` from PATH", script)

    def test_linux_offline_build_uses_image_tools_offline_bundle_mode(self) -> None:
        script = LINUX_OFFLINE_BUILD.read_text(encoding="utf-8")

        self.assertIn("-m paper_fetch.image_tools.install", script)
        self.assertIn("--offline-bundle", script)
        self.assertIn('--repo-root "$REPO_DIR"', script)


if __name__ == "__main__":
    unittest.main()
