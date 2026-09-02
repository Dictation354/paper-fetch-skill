from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest

import pytest

from ._installer_support import write_executable as _write_executable
from scripts.skill_integrity import build_skill_bundle_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
LINUX_INSTALLER = REPO_ROOT / "install-offline.sh"
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


def _fake_python_script(
    version: str,
    *,
    machine: str = "x86_64",
    soabi: str | None = None,
    abi_flags: str = "",
    gil_disabled: bool = False,
) -> str:
    tag = _python_tag(version)
    soabi = soabi or f"cpython-{tag.removeprefix('cp')}-test"
    real_python = shlex.quote(sys.executable)
    return f"""\
    #!/usr/bin/env bash
    set -euo pipefail
    VERSION="{version}"
    TAG="{tag}"
    MACHINE="{machine}"
    SOABI="{soabi}"
    ABI_FLAGS="{abi_flags or "-"}"
    GIL_DISABLED="{int(gil_disabled)}"
    REAL_PYTHON={real_python}

    if [[ "${{1:-}}" == "-I" && "${{2:-}}" == "-" ]]; then
      shift
      code="$(cat)"
      exec "$REAL_PYTHON" -I "$@" <<< "$code"
    fi

    if [[ "${{1:-}}" == "-I" && "${{2:-}}" == "-c" ]]; then
      shift
    fi

    while [[ "${{1:-}}" == "-X" ]]; do
      shift 2
    done

    if [[ "${{1:-}}" == */scripts/skill_integrity.py ]]; then
      export PYTHONDONTWRITEBYTECODE=1
      exec "$REAL_PYTHON" "$@"
    fi

    if [[ "${{1:-}}" == "-c" ]]; then
      code="${{2:-}}"
      if [[ "$code" == *'PAPER_FETCH_INTERPRETER_PROBE'* ]]; then
        printf '%s|cpython|%s|%s|%s|%s|%s\\n' \
          "$VERSION" "$TAG" "$MACHINE" "$SOABI" "$ABI_FLAGS" "$GIL_DISABLED"
        exit 0
      fi
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
            target.minimum_os_version)
              grep -oE '"minimum_os_version"[[:space:]]*:[[:space:]]*"[^"]+"' "$manifest" | head -n 1 | sed -E 's/.*"minimum_os_version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\\1/'
              ;;
          esac
        fi
        exit 0
      fi
      if [[ "$code" == *'installer_manifest_values'* ]]; then
        exec "$REAL_PYTHON" -I "$@"
      fi
      if [[ "$code" == *'camoufox'* ]]; then
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


def _fake_sw_vers_script(product_version: str) -> str:
    return f"""\
    #!/usr/bin/env bash
    case "${{1:-}}" in
      -productVersion) printf '%s\\n' "{product_version}" ;;
      *) printf 'ProductVersion:\\t%s\\n' "{product_version}" ;;
    esac
    """


def _fake_xattr_script() -> str:
    return """\
    #!/usr/bin/env bash
    if [[ "${PAPER_FETCH_TEST_XATTR_ERROR:-0}" == "1" ]]; then
      printf 'xattr: simulated permission denied\\n' >&2
      exit 77
    fi
    if [[ "${1:-}" == "-r" && "${2:-}" == "-s" && "${3:-}" == "-v" ]]; then
      root="${4:-}"
      candidate="${PAPER_FETCH_TEST_QUARANTINED_PATH:-}"
      if [[ -n "$candidate" && "$candidate" == "$root"/* ]]; then
        printf '%s: com.apple.quarantine\\n' "$candidate"
      fi
      noise_lines="${PAPER_FETCH_TEST_XATTR_NOISE_LINES:-0}"
      for ((index = 0; index < noise_lines; index += 1)); do
        printf '%s/noise-%08d: com.apple.provenance\\n' "$root" "$index"
      done
      exit 0
    fi
    exit 1
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


@pytest.mark.allow_subprocess
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
        minimum_macos_version: str | None = "15.0",
        host_macos_version: str = "15.0",
        python_machine: str | None = None,
        python_soabi: str | None = None,
        python_abi_flags: str = "",
        python_gil_disabled: bool = False,
    ) -> tuple[Path, Path, Path]:
        bundle = root / "bundle"
        bundle.mkdir()
        shutil.copy2(REPO_ROOT / "install-offline.sh", bundle / "install-offline.sh")
        (bundle / "install-offline.sh").chmod(0o755)
        shutil.copytree(REPO_ROOT / "installer", bundle / "installer")

        manifest_python_tag = manifest_python_tag or _python_tag(python_version)
        python_machine = python_machine or target_arch
        _write_file(bundle / ".env.example", 'ELSEVIER_API_KEY=""\n')
        _write_file(
            bundle / "runtime" / "site-packages" / "paper_fetch" / "__init__.py", "\n"
        )
        (bundle / "scripts").mkdir()
        shutil.copy2(
            REPO_ROOT / "scripts" / "skill_integrity.py",
            bundle / "scripts" / "skill_integrity.py",
        )
        _write_file(
            bundle / "runtime" / "site-packages" / "camoufox" / "__init__.py", "\n"
        )
        _write_executable(
            bundle / "runtime" / "site-packages" / "playwright" / "driver" / "node",
            "#!/usr/bin/env bash\nexit 0\n",
        )
        _write_executable(
            bundle / "runtime" / "paper-fetch-python",
            _fake_python_script(
                python_version,
                machine=python_machine,
                soabi=python_soabi,
                abi_flags=python_abi_flags,
                gil_disabled=python_gil_disabled,
            ),
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

        skill_dir = bundle / "skills" / "paper-fetch-skill"
        target = {
            "platform": target_platform,
            "arch": target_arch,
            "python_tag": manifest_python_tag,
        }
        if target_platform == "macos" and minimum_macos_version is not None:
            target["minimum_os_version"] = minimum_macos_version

        manifest = {
            "schema_version": 3,
            "name": "paper-fetch-skill-offline-linux-x86_64",
            "project": "paper-fetch-skill",
            "version": "3.1.3",
            "built_at_utc": "2026-07-15T00:00:00Z",
            "git_revision": "test-revision",
            "target": target,
            "entrypoint": "install-offline.sh",
            "skill_bundle": build_skill_bundle_manifest(
                skill_dir,
                name="paper-fetch-skill",
                root="skills/paper-fetch-skill",
            ),
        }
        _write_file(
            bundle / "offline-manifest.json",
            json.dumps(manifest, indent=2) + "\n",
        )

        fake_bin = root / "fake-bin"
        _write_executable(
            fake_bin / "python3",
            _fake_python_script(
                python_version,
                machine=python_machine,
                soabi=python_soabi,
                abi_flags=python_abi_flags,
                gil_disabled=python_gil_disabled,
            ),
        )
        _write_executable(
            fake_bin / "uname", _fake_uname_script(uname_kernel, uname_machine)
        )
        if uname_kernel == "Darwin":
            _write_executable(
                fake_bin / "sw_vers", _fake_sw_vers_script(host_macos_version)
            )
            _write_executable(fake_bin / "xattr", _fake_xattr_script())

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
        install_dir: Path | str | None = None,
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

    def test_default_install_writes_browser_runtime_env_hint(self) -> None:
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
            self.assertNotIn("PAPER_FETCH_BROWSER_USER_AGENT", offline_env)
            self.assertNotIn("CLOAKBROWSER_", offline_env)
            self.assertIn('PAPER_FETCH_BROWSER_HEADLESS="true"', offline_env)
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
            self.assertIn(
                "Default browser backend: Camoufox (headless: true)", result.stdout
            )

    def test_schema_v1_legacy_env_sets_do_not_override_canonical_mcp_keys(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            manifest_path = bundle / "installer" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["env_sets"] = {
                "offline_env_keys": ["LEGACY_UNUSED_ENV"],
                "shell_env_keys": ["LEGACY_UNUSED_ENV"],
                "activate_env_keys": ["LEGACY_UNUSED_ENV"],
            }
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            _write_checksums(bundle)

            result = self._run_installer(bundle, fake_bin, home)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(
                "LEGACY_UNUSED_ENV",
                (bundle / "offline.env").read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                "LEGACY_UNUSED_ENV",
                (bundle / "activate-offline.sh").read_text(encoding="utf-8"),
            )
            self.assertNotIn(
                "LEGACY_UNUSED_ENV", (home / ".bashrc").read_text(encoding="utf-8")
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
            initial = self._run_installer(
                bundle, fake_bin, home, install_dir=install_root
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)

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

    def test_install_rejects_home_before_removing_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            sentinel = home / "src" / "keep.txt"
            _write_file(sentinel, "keep\n")

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=home,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing to install into HOME", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertFalse((home / ".bashrc").exists())
            self.assertFalse((home / ".codex").exists())

    def test_install_rejects_nonempty_unowned_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            install_root = root / "unowned"
            sentinel = install_root / "src" / "keep.txt"
            _write_file(sentinel, "keep\n")

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-empty unowned install directory", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertFalse((home / ".bashrc").exists())
            self.assertFalse((home / ".codex").exists())

    def test_install_rejects_home_ancestor_before_removing_existing_content(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            sentinel = root / "keep.txt"
            _write_file(sentinel, "keep\n")

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=root,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ancestor of HOME", result.stderr)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue(bundle.is_dir())
            self.assertFalse((home / ".bashrc").exists())
            self.assertFalse((home / ".codex").exists())

    def test_install_rejects_symlink_to_nonempty_unowned_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            actual_target = root / "actual-unowned"
            sentinel = actual_target / "src" / "keep.txt"
            _write_file(sentinel, "keep\n")
            install_link = root / "install-link"
            install_link.symlink_to(actual_target, target_is_directory=True)

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_link,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-empty unowned install directory", result.stderr)
            self.assertTrue(install_link.is_symlink())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertFalse((home / ".bashrc").exists())

    def test_install_allows_existing_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            install_root = root / "empty"
            install_root.mkdir()

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((install_root / "runtime" / "python-bin").is_file())

    def test_shell_startup_blocks_set_headless_without_legacy_browser_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            bash_install = root / "bash-install"
            fish_install = root / "fish-install"

            bash_result = self._run_installer(
                bundle,
                fake_bin,
                home,
                shell="/bin/bash",
                install_dir=bash_install,
            )
            fish_result = self._run_installer(
                bundle,
                fake_bin,
                home,
                shell="/usr/bin/fish",
                install_dir=fish_install,
            )

            self.assertEqual(bash_result.returncode, 0, bash_result.stderr)
            self.assertEqual(fish_result.returncode, 0, fish_result.stderr)
            bashrc = (home / ".bashrc").read_text(encoding="utf-8")
            fish_config = (
                home / ".config" / "fish" / "conf.d" / "paper-fetch-offline.fish"
            ).read_text(encoding="utf-8")
            self.assertIn(
                f'export PAPER_FETCH_ENV_FILE="{bash_install / "offline.env"}"',
                bashrc,
            )
            self.assertIn(
                f'set -gx PAPER_FETCH_ENV_FILE "{fish_install / "offline.env"}"',
                fish_config,
            )
            self.assertIn(
                f'export PAPER_FETCH_IMAGE_TOOLS_DIR="{bash_install / "image-tools"}"',
                bashrc,
            )
            self.assertIn(
                f'set -gx PAPER_FETCH_IMAGE_TOOLS_DIR "{fish_install / "image-tools"}"',
                fish_config,
            )
            self.assertIn('export PAPER_FETCH_BROWSER_HEADLESS="true"', bashrc)
            self.assertIn('set -gx PAPER_FETCH_BROWSER_HEADLESS "true"', fish_config)
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
            self.assertNotIn("CLOAKBROWSER_", offline_env)
            self.assertIn('PAPER_FETCH_BROWSER_HEADLESS="false"', offline_env)
            self.assertIn(
                "Default browser backend: Camoufox (headless: false)", result.stdout
            )

    def test_macos_host_below_manifest_minimum_is_rejected_before_writes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(
                root,
                python_version="3.14.0",
                target_platform="macos",
                target_arch="arm64",
                uname_kernel="Darwin",
                uname_machine="arm64",
                minimum_macos_version="15.0",
                host_macos_version="14.7.5",
            )
            install_root = root / "installed"

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
                shell="/bin/zsh",
            )

            self.assertNotEqual(result.returncode, 0)
            diagnostic = result.stdout + result.stderr
            self.assertIn("requires macOS 15.0 or newer", diagnostic)
            self.assertIn("detected macOS 14.7.5", diagnostic)
            self.assertFalse(install_root.exists())
            self.assertFalse((home / ".zshrc").exists())
            self.assertFalse((home / ".codex").exists())

    def test_macos_rejects_rosetta_python_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(
                root,
                python_version="3.14.0",
                target_platform="macos",
                target_arch="arm64",
                uname_kernel="Darwin",
                uname_machine="arm64",
                python_machine="x86_64",
                python_soabi="cpython-314-darwin",
            )
            install_root = root / "installed"

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
                shell="/bin/zsh",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "requires Python interpreter architecture arm64", result.stderr
            )
            self.assertIn("detected x86_64", result.stderr)
            self.assertFalse(install_root.exists())
            self.assertFalse((home / ".zshrc").exists())
            self.assertFalse((home / ".codex").exists())

    def test_macos_rejects_nonstandard_cpython_abi_before_writes(self) -> None:
        cases = (
            {
                "name": "free-threaded",
                "python_soabi": "cpython-314t-darwin",
                "python_abi_flags": "t",
                "python_gil_disabled": True,
                "diagnostic": "standard GIL CPython",
            },
            {
                "name": "debug",
                "python_soabi": "cpython-314d-darwin",
                "python_abi_flags": "d",
                "python_gil_disabled": False,
                "diagnostic": "standard GIL CPython",
            },
            {
                "name": "nonstandard-soabi",
                "python_soabi": "custom-314-darwin",
                "python_abi_flags": "",
                "python_gil_disabled": False,
                "diagnostic": "standard SOABI cpython-314-*",
            },
        )
        for case in cases:
            with (
                self.subTest(case=case["name"]),
                tempfile.TemporaryDirectory() as tmpdir,
            ):
                root = Path(tmpdir)
                bundle, fake_bin, home = self._create_bundle(
                    root,
                    python_version="3.14.0",
                    target_platform="macos",
                    target_arch="arm64",
                    uname_kernel="Darwin",
                    uname_machine="arm64",
                    python_machine="arm64",
                    python_soabi=case["python_soabi"],
                    python_abi_flags=case["python_abi_flags"],
                    python_gil_disabled=case["python_gil_disabled"],
                )
                install_root = root / "installed"

                result = self._run_installer(
                    bundle,
                    fake_bin,
                    home,
                    install_dir=install_root,
                    shell="/bin/zsh",
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(case["diagnostic"], result.stderr)
                self.assertFalse(install_root.exists())
                self.assertFalse((home / ".zshrc").exists())
                self.assertFalse((home / ".codex").exists())

    def test_macos_quarantine_fails_before_user_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(
                root,
                target_platform="macos",
                target_arch="arm64",
                uname_kernel="Darwin",
                uname_machine="arm64",
            )
            install_root = root / "installed"
            quarantined_library = bundle / "formula-tools" / "lib" / "libgmp.dylib"
            _write_file(quarantined_library, "fake dylib\n")
            _write_checksums(bundle)

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
                shell="/bin/zsh",
                extra_env={
                    "PAPER_FETCH_TEST_QUARANTINED_PATH": str(quarantined_library),
                    # A real bundle can emit megabytes of provenance attributes.
                    # The quarantine match must not be lost to pipefail/SIGPIPE
                    # when grep exits after an early match.
                    "PAPER_FETCH_TEST_XATTR_NOISE_LINES": "20000",
                },
            )

            self.assertNotEqual(result.returncode, 0)
            diagnostic = result.stdout + result.stderr
            self.assertIn("macOS quarantine is present", diagnostic)
            self.assertIn("within the offline bundle", diagnostic)
            self.assertIn("xattr -dr com.apple.quarantine", diagnostic)
            self.assertFalse(install_root.exists())
            self.assertFalse((home / ".zshrc").exists())
            self.assertFalse((home / ".codex").exists())

    def test_macos_checksum_failure_precedes_quarantine_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(
                root,
                target_platform="macos",
                target_arch="arm64",
                uname_kernel="Darwin",
                uname_machine="arm64",
            )
            quarantined_node = (
                bundle / "runtime" / "site-packages" / "playwright" / "driver" / "node"
            )
            quarantined_node.write_text("tampered\n", encoding="utf-8")
            install_root = root / "installed"

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
                shell="/bin/zsh",
                extra_env={"PAPER_FETCH_TEST_QUARANTINED_PATH": str(quarantined_node)},
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Verifying bundled file checksums", result.stdout)
            self.assertNotIn("macOS quarantine is present", result.stderr)
            self.assertFalse(install_root.exists())
            self.assertFalse((home / ".zshrc").exists())

    def test_unlisted_runtime_payload_is_rejected_before_bundled_python_runs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            install_root = root / "installed"
            execution_sentinel = root / "sitecustomize-ran"
            injected = bundle / "runtime" / "site-packages" / "sitecustomize.py"
            _write_file(
                injected,
                "from pathlib import Path\n"
                f"Path({str(execution_sentinel)!r}).write_text('ran', encoding='utf-8')\n",
            )

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unlisted payload file(s)", result.stderr)
            self.assertIn("runtime/site-packages/sitecustomize.py", result.stderr)
            self.assertFalse(execution_sentinel.exists())
            self.assertFalse(install_root.exists())
            self.assertFalse((home / ".bashrc").exists())
            self.assertFalse((home / ".codex").exists())

    @unittest.skipUnless(
        sys.platform.startswith(("linux", "darwin")),
        "POSIX installer regression",
    )
    def test_unlisted_top_level_sitecustomize_is_rejected_before_host_python_import(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            machine = platform.machine().lower()
            target_arch = {"amd64": "x86_64", "aarch64": "arm64"}.get(machine, machine)
            target_platform = "macos" if sys.platform == "darwin" else "linux"
            uname_kernel = "Darwin" if target_platform == "macos" else "Linux"
            bundle, fake_bin, home = self._create_bundle(
                root,
                target_platform=target_platform,
                target_arch=target_arch,
                manifest_python_tag=_python_tag(platform.python_version()),
                uname_kernel=uname_kernel,
                uname_machine=target_arch,
            )
            install_root = root / "installed"
            execution_sentinel = root / "sitecustomize-ran"
            _write_file(
                bundle / "sitecustomize.py",
                "from pathlib import Path\n"
                f"Path({str(execution_sentinel)!r}).write_text('ran', encoding='utf-8')\n",
            )

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
                extra_env={
                    "PAPER_FETCH_OFFLINE_PYTHON_BIN": sys.executable,
                    "PYTHONPATH": str(bundle),
                },
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unlisted payload file(s)", result.stderr)
            self.assertIn("sitecustomize.py", result.stderr)
            self.assertFalse(execution_sentinel.exists())
            self.assertFalse(install_root.exists())
            self.assertFalse((home / ".bashrc").exists())
            self.assertFalse((home / ".codex").exists())

    def test_macos_xattr_inspection_error_fails_closed_before_user_writes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(
                root,
                target_platform="macos",
                target_arch="arm64",
                uname_kernel="Darwin",
                uname_machine="arm64",
            )
            install_root = root / "installed"

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
                shell="/bin/zsh",
                extra_env={"PAPER_FETCH_TEST_XATTR_ERROR": "1"},
            )

            self.assertNotEqual(result.returncode, 0)
            diagnostic = result.stdout + result.stderr
            self.assertIn(
                "Could not recursively inspect macOS quarantine attributes",
                diagnostic,
            )
            self.assertIn("simulated permission denied", diagnostic)
            self.assertFalse(install_root.exists())
            self.assertFalse((home / ".zshrc").exists())
            self.assertFalse((home / ".codex").exists())

    def test_macos_user_config_uses_application_support(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(
                Path(tmpdir),
                target_platform="macos",
                target_arch="arm64",
                uname_kernel="Darwin",
                uname_machine="arm64",
            )
            macos_env = (
                home / "Library" / "Application Support" / "paper-fetch" / ".env"
            )
            _write_file(macos_env, 'USER_NOTE="keep"\n')

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--user-config",
                shell="/bin/zsh",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(macos_env.is_file())
            self.assertIn(
                f'PAPER_FETCH_DOWNLOAD_DIR="{bundle / "downloads"}"',
                macos_env.read_text(encoding="utf-8"),
            )
            self.assertFalse((home / ".config" / "paper-fetch" / ".env").exists())

            uninstall = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--uninstall",
                shell="/bin/zsh",
            )

            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            uninstalled_env = macos_env.read_text(encoding="utf-8")
            self.assertIn('USER_NOTE="keep"', uninstalled_env)
            self.assertNotIn("# BEGIN paper-fetch offline managed", uninstalled_env)

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
            self.assertIn("PAPER_FETCH_BROWSER_HEADLESS=true", codex_add)
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
            self.assertIn('PAPER_FETCH_BROWSER_HEADLESS = "true"', config)
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

    def test_zsh_startup_symlink_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            zsh_target = home / "config" / "zshrc"
            _write_file(zsh_target, "keep zsh setting\n")
            zsh_link = home / ".zshrc"
            zsh_link.symlink_to(Path("config") / "zshrc")

            result = self._run_installer(bundle, fake_bin, home, shell="/bin/zsh")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(zsh_link.is_symlink())
            installed_content = zsh_target.read_text(encoding="utf-8")
            self.assertIn("keep zsh setting", installed_content)
            self.assertIn("# BEGIN paper-fetch offline managed", installed_content)

            uninstall = self._run_installer(
                bundle, fake_bin, home, "--uninstall", shell="/bin/zsh"
            )

            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertTrue(zsh_link.is_symlink())
            uninstalled_content = zsh_target.read_text(encoding="utf-8")
            self.assertIn("keep zsh setting", uninstalled_content)
            self.assertNotIn("# BEGIN paper-fetch offline managed", uninstalled_content)

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
            linux_user_env = home / ".config" / "paper-fetch" / ".env"
            _write_file(
                linux_user_env,
                f'USER_NOTE="keep"\n{managed}',
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
            self.assertEqual(
                linux_user_env.read_text(encoding="utf-8"),
                'USER_NOTE="keep"\n',
            )
            calls = [
                line.split("\t")
                for line in cli_log.read_text(encoding="utf-8").splitlines()
            ]
            self.assertIn(["codex", "mcp", "remove", "paper-fetch"], calls)
            self.assertFalse(any(call[:3] == ["codex", "mcp", "add"] for call in calls))
            self.assertIn("Install directory was left in place", result.stdout)

    def test_uninstall_without_installer_manifest_keeps_default_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            managed = textwrap.dedent(
                """
                keep before
                # BEGIN paper-fetch offline managed
                export PAPER_FETCH_ENV_FILE="/old/offline.env"
                # END paper-fetch offline managed
                keep after
                """
            ).lstrip()
            _write_file(home / ".bashrc", managed)
            (bundle / "installer" / "manifest.json").unlink()

            result = self._run_installer(bundle, fake_bin, home, "--uninstall")

            self.assertEqual(result.returncode, 0, result.stderr)
            startup = (home / ".bashrc").read_text(encoding="utf-8")
            self.assertIn("keep before", startup)
            self.assertIn("keep after", startup)
            self.assertNotIn("# BEGIN paper-fetch offline managed", startup)

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

    def test_purge_from_installed_copy_allows_owned_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            install_root = root / "installed"
            result = self._run_installer(
                bundle, fake_bin, home, install_dir=install_root
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            purge = self._run_installer(
                install_root,
                fake_bin,
                home,
                "--purge",
                install_dir=install_root,
            )

            self.assertEqual(purge.returncode, 0, purge.stderr)
            self.assertFalse(install_root.exists())
            self.assertIn("Install directory deleted", purge.stdout)

    def test_purge_normalizes_owned_dot_path_before_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            install_root = root / "installed"
            result = self._run_installer(
                bundle, fake_bin, home, install_dir=install_root
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            purge = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--purge",
                install_dir=f"{install_root}/.",
            )

            self.assertEqual(purge.returncode, 0, purge.stderr)
            self.assertFalse(install_root.exists())
            self.assertIn(f"Install directory deleted: {install_root}", purge.stdout)

    def test_purge_rejects_owned_symlink_before_removing_integrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            install_root = root / "installed"
            initial = self._run_installer(
                bundle,
                fake_bin,
                home,
                install_dir=install_root,
            )
            self.assertEqual(initial.returncode, 0, initial.stderr)
            sentinel = install_root / "keep.txt"
            _write_file(sentinel, "keep\n")
            install_link = root / "installed-link"
            install_link.symlink_to(install_root, target_is_directory=True)
            installed_skill = (
                home / ".codex" / "skills" / "paper-fetch-skill" / "SKILL.md"
            )
            self.assertTrue(installed_skill.is_file())

            purge = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--purge",
                install_dir=f"{install_link}/.",
            )

            self.assertNotEqual(purge.returncode, 0)
            self.assertIn("symbolic-link install directory", purge.stderr)
            self.assertTrue(install_link.is_symlink())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue(installed_skill.is_file())

    def test_purge_rejects_uninstalled_bundle_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--purge",
                install_dir=bundle,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "without the runtime/python-bin installer marker", result.stderr
            )
            self.assertTrue(bundle.is_dir())

    def test_purge_requires_install_marker_for_every_owned_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            uninstalled_target = root / "other-unpacked-bundle"
            uninstalled_target.mkdir()
            shutil.copy2(
                bundle / "offline-manifest.json",
                uninstalled_target / "offline-manifest.json",
            )
            sentinel = uninstalled_target / "keep.txt"
            _write_file(sentinel, "keep\n")
            skill = home / ".codex" / "skills" / "paper-fetch-skill" / "SKILL.md"
            _write_file(skill, "owned user skill\n")

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--purge",
                install_dir=uninstalled_target,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "without the runtime/python-bin installer marker",
                result.stderr,
            )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep\n")
            self.assertTrue(skill.is_file())

    def test_purge_rejects_home_before_removing_integrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            managed = textwrap.dedent(
                """
                keep setting
                # BEGIN paper-fetch offline managed
                export PAPER_FETCH_ENV_FILE="/old/offline.env"
                # END paper-fetch offline managed
                """
            ).lstrip()
            _write_file(home / ".zshrc", managed)
            skill = home / ".codex" / "skills" / "paper-fetch-skill" / "SKILL.md"
            _write_file(skill, "owned user skill\n")

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--purge",
                install_dir=home,
                shell="/bin/zsh",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing to purge HOME", result.stderr)
            self.assertTrue(home.is_dir())
            self.assertTrue(skill.is_file())
            self.assertEqual((home / ".zshrc").read_text(encoding="utf-8"), managed)

    def test_purge_rejects_home_ancestor_before_removing_integrations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            skill = home / ".codex" / "skills" / "paper-fetch-skill" / "SKILL.md"
            _write_file(skill, "owned user skill\n")

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--purge",
                install_dir=root,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ancestor of HOME", result.stderr)
            self.assertTrue(root.is_dir())
            self.assertTrue(skill.is_file())

    def test_purge_requires_owned_target_manifest_before_removing_integrations(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bundle, fake_bin, home = self._create_bundle(root)
            unowned_target = root / "unowned"
            _write_file(unowned_target / "keep.txt", "keep\n")
            skill = home / ".codex" / "skills" / "paper-fetch-skill" / "SKILL.md"
            _write_file(skill, "owned user skill\n")

            result = self._run_installer(
                bundle,
                fake_bin,
                home,
                "--purge",
                install_dir=unowned_target,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("without an owned offline-manifest.json", result.stderr)
            self.assertTrue((unowned_target / "keep.txt").is_file())
            self.assertTrue(skill.is_file())

    def test_matching_manifest_and_interpreter_tags_are_accepted(self) -> None:
        for python_version, python_tag in (
            ("3.11.9", "cp311"),
            ("3.12.7", "cp312"),
            ("3.13.3", "cp313"),
            ("3.14.0", "cp314"),
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

    def test_skill_hash_drift_is_rejected_after_bundle_checksum_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            reference = (
                bundle
                / "skills"
                / "paper-fetch-skill"
                / "references"
                / "tool-contract.md"
            )
            reference.write_text("changed after manifest\n", encoding="utf-8")
            _write_checksums(bundle)

            result = self._run_installer(bundle, fake_bin, home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("skill bundle integrity check failed", result.stderr)
            self.assertIn("references/tool-contract.md", result.stderr)

    def test_missing_skill_reference_is_rejected_after_checksum_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle, fake_bin, home = self._create_bundle(Path(tmpdir))
            reference = (
                bundle
                / "skills"
                / "paper-fetch-skill"
                / "references"
                / "tool-contract.md"
            )
            reference.unlink()
            _write_checksums(bundle)

            result = self._run_installer(bundle, fake_bin, home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("skill bundle integrity check failed", result.stderr)
            self.assertIn("references/tool-contract.md", result.stderr)

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

    def test_linux_installer_does_not_call_playwright_browser_install(self) -> None:
        linux_script = LINUX_INSTALLER.read_text(encoding="utf-8")

        self.assertNotIn("python -m playwright install chromium", linux_script)
        self.assertNotIn("-m playwright install chromium", linux_script)
        self.assertNotIn("camoufox.ensure_runtime()", linux_script)
        self.assertNotIn('assert hasattr(camoufox, "launch")', linux_script)
        self.assertIn(
            "from paper_fetch.providers.browser_runtime.camoufox_manager import "
            "CamoufoxBrowserManager",
            linux_script,
        )

    def test_windows_installer_helper_uses_camoufox_runtime_smoke(self) -> None:
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
        self.assertIn("import camoufox", script)
        self.assertIn("import camoufox", script)
        self.assertIn("import playwright", script)
        self.assertIn(
            "from paper_fetch.providers.browser_runtime.camoufox_manager import "
            "CamoufoxBrowserManager",
            script,
        )
        self.assertIn('assert hasattr(camoufox, "Camoufox")', script)
        self.assertNotIn('assert hasattr(camoufox, "launch")', script)
        self.assertNotIn("PAPER_FETCH_BROWSER_USER_AGENT", script)
        self.assertIn("$OfflineEnvKeys = @(", script)
        self.assertIn("$manifest.mcp.env_keys", script)
        self.assertIn('Where-Object { $_ -ne "PAPER_FETCH_ENV_FILE" }', script)
        self.assertIn("Format-DotenvAssignment", script)
        self.assertNotIn("CLOAKBROWSER_", script)
        self.assertNotIn("probe-launch", script)
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", script)
        self.assertIn("PAPER_FETCH_IMAGE_TOOLS_DIR", script)
        self.assertIn("playwright/driver/node.exe", script)
        self.assertIn('PAPER_FETCH_BROWSER_HEADLESS = "true"', script)
        self.assertIn("PAPER_FETCH_BROWSER_HEADLESS", script)
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
        self.assertIn("function Test-SkillBundleIntegrity", script)
        self.assertIn('Join-Path $InstallRoot "scripts/skill_integrity.py"', script)
        self.assertIn('Name "bundled skill integrity" -Required', script)
        self.assertIn('Name "skill installation" -Required', script)

    def test_windows_inno_installer_preserves_user_payload_and_restores_offline_env_before_helper(
        self,
    ) -> None:
        script = WINDOWS_INNO_INSTALLER.read_text(encoding="utf-8")

        self.assertIn("BackupOfflineEnv", script)
        self.assertIn("RunOldUninstaller", script)
        self.assertIn("CleanOldInstallDirectory", script)
        self.assertIn("RestoreOfflineEnv", script)
        self.assertIn('Source: "vendor\\uninsis\\i386\\UninsIS.dll"', script)
        self.assertIn("IsISPackageInstalled@files:UninsIS.dll", script)
        self.assertIn("UninstallISPackage@files:UninsIS.dll", script)
        self.assertIn("completed and deleted its original executable", script)
        self.assertIn("UninsIS-LGPL-3.0.txt", script)
        self.assertIn("UninsIS-NOTICE.md", script)
        self.assertNotIn("QuietUninstallString", script)
        self.assertNotIn("QueryOldUninstallCommand", script)
        self.assertNotIn("SplitCommandLine", script)
        self.assertIn("RemoveDir(AppDir)", script)
        self.assertNotIn("DelTree(AppDir, True, True, True)", script)
        self.assertIn("Preserving user-owned content", script)
        self.assertIn("onlyifdoesntexist uninsneveruninstall", script)
        self.assertIn("function PrepareToInstall", script)
        self.assertIn("Result := PrepareUpgradeInstall", script)
        self.assertNotIn("CurStep = ssInstall", script)
        self.assertIn("CurStep = ssPostInstall", script)
        self.assertIn("RunPostInstallHelper", script)
        self.assertIn(
            "HelperPath := ExpandConstant('{app}\\scripts\\windows-installer-helper.ps1')",
            script,
        )
        self.assertIn("PostInstallHelperWarning := True", script)
        self.assertIn("install-helper.log", script)
        self.assertIn("[UninstallDelete]", script)
        self.assertIn('Type: files; Name: "{app}\\install-helper.log"', script)
        self.assertIn('-LogPath "', script)
        self.assertIn('" -Action Install', script)
        self.assertIn("RestoreOfflineEnv;\n    RunPostInstallHelper;", script)
        self.assertNotIn(
            "Paper Fetch Skill post-install helper failed with exit code", script
        )

    def test_installer_manifest_has_one_canonical_runtime_env_set(self) -> None:
        manifest = json.loads(
            (REPO_ROOT / "installer" / "manifest.json").read_text(encoding="utf-8")
        )

        mcp_env_keys = manifest["mcp"]["env_keys"]
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["skill"], {"name": "paper-fetch-skill"})
        self.assertNotIn("env_sets", manifest)
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", mcp_env_keys)
        self.assertIn("PAPER_FETCH_IMAGE_TOOLS_DIR", mcp_env_keys)
        installer = LINUX_INSTALLER.read_text(encoding="utf-8")
        self.assertIn('SHELL_ENV_KEYS=("${MCP_ENV_KEYS[@]}")', installer)
        self.assertIn('ACTIVATE_ENV_KEYS=("${MCP_ENV_KEYS[@]}")', installer)
        self.assertIn('[ "$key" != "PAPER_FETCH_ENV_FILE" ]', installer)

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
