from __future__ import annotations
import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "build-offline-package.sh"
BUILD_OFFLINE_PACKAGE_WINDOWS = (
    REPO_ROOT / "scripts" / "build-offline-package-windows.ps1"
)
VERIFY_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "verify-offline-package.sh"


def _shell_function(script: str, name: str, next_name: str) -> str:
    start = script.index(f"{name}()")
    end = script.index(f"{next_name}()", start)
    return script[start:end]


class OfflinePackageBuildTests(unittest.TestCase):
    def test_posix_staging_cleanup_requires_unpacked_ownership_marker(
        self,
    ) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        checksums_block = _shell_function(
            script,
            "write_checksums",
            "write_manifest_and_checksums",
        )
        self_extract_block = _shell_function(
            script,
            "create_self_extracting_installer",
            "create_archive",
        )
        archive_block = _shell_function(script, "create_archive", "main")
        runtime_block = _shell_function(
            script,
            "build_project_runtime",
            "verify_macos_arm64_binary",
        )

        self.assertIn("prepare_owned_staging", script)
        self.assertIn("staging_is_owned", script)
        self.assertIn("$staging/.paper-fetch-build-support", runtime_block)
        self.assertIn('staging_is_owned "$staging" "$package_name"', runtime_block)
        self.assertNotIn("$BUILD_DIR/project-dist", runtime_block)
        self.assertNotIn("$BUILD_DIR/linux-runtime-wheelhouse", runtime_block)
        self.assertIn("STAGING_OWNERSHIP_MARKER_NAME", checksums_block)
        self.assertIn(
            '--exclude="$package_name/$STAGING_OWNERSHIP_MARKER_NAME"',
            self_extract_block,
        )
        self.assertIn(
            '--exclude="$package_name/$STAGING_OWNERSHIP_MARKER_NAME"',
            archive_block,
        )

    def test_posix_self_extractor_exits_normally_to_run_cleanup_trap(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        self_extract_block = _shell_function(
            script,
            "create_self_extracting_installer",
            "create_archive",
        )

        self.assertIn("trap cleanup EXIT", self_extract_block)
        self.assertNotIn(
            'exec "$payload_root/install-offline.sh" "$@"',
            self_extract_block,
        )
        self.assertIn("status=$?", self_extract_block)
        self.assertIn('exit "$status"', self_extract_block)

    def test_posix_release_publish_uses_atomic_output_directory_temporary(
        self,
    ) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        blocks = (
            _shell_function(
                script,
                "create_self_extracting_installer",
                "create_archive",
            ),
            _shell_function(script, "create_archive", "main"),
        )

        for block in blocks:
            self.assertIn('mktemp "$output_dir/', block)
            self.assertIn("trap cleanup_release_temporaries EXIT", block)
            self.assertIn("os.replace(sys.argv[1], sys.argv[2])", block)
            self.assertNotIn('rm -f "$output_path"', block)
        self.assertIn('chmod 0644 "$temporary_output"', blocks[1])

    def test_posix_build_uses_resolved_camoufox_wheel_version(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        runtime_block = _shell_function(
            script,
            "build_project_runtime",
            "verify_macos_arm64_binary",
        )

        self.assertNotIn("locked_camoufox_version()", script)
        self.assertNotIn('"camoufox==$CAMOUFOX_PYTHON_PACKAGE_VERSION"', runtime_block)
        self.assertIn('CAMOUFOX_PYTHON_PACKAGE_VERSION="$(', runtime_block)
        self.assertIn('[ "${#camoufox_wheels[@]}" -eq 1 ]', runtime_block)
        self.assertIn("from email.parser import BytesParser", runtime_block)
        self.assertIn("from zipfile import ZipFile", runtime_block)
        self.assertIn(
            "Camoufox dependency wheel has no version",
            runtime_block,
        )
        self.assertIn("from importlib.metadata import distributions", runtime_block)
        self.assertIn(
            "distributions(path=[str(site_packages)])",
            runtime_block,
        )
        self.assertIn(
            "Installed Camoufox runtime must match resolved wheel version",
            runtime_block,
        )

    def test_posix_manifest_records_verified_camoufox_version(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        manifest_block = _shell_function(
            script,
            "write_manifest_and_checksums",
            "create_self_extracting_installer",
        )

        self.assertIn("resolved_camoufox_version = sys.argv[10]", manifest_block)
        self.assertIn(
            "distributions(path=[str(site_packages)])",
            manifest_block,
        )
        self.assertIn(
            '"python_package_version": camoufox_version',
            manifest_block,
        )

    def test_posix_package_build_creates_installed_runtime_package(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")

        self.assertIn("copy_runtime_assets", script)
        self.assertIn("create_self_extracting_installer", script)
        self.assertIn("__PAPER_FETCH_OFFLINE_PAYLOAD_BELOW__", script)
        self.assertIn("create_archive", script)
        self.assertIn("macos_offline_name_prefix", script)
        self.assertIn("runtime/site-packages", script)
        self.assertIn("runtime/python-bin", script)
        self.assertIn("$runtime/paper-fetch-python", script)
        self.assertIn("write_cmd_wrappers", script)
        self.assertIn("$bin/paper-fetch", script)
        self.assertIn("$bin/paper-fetch-install-formula-tools", script)
        self.assertIn("camoufox-*.whl", script)
        self.assertIn("Expected one Camoufox dependency wheel", script)
        self.assertIn("-m compileall", script)
        self.assertNotIn("copy_source_snapshot", script)
        self.assertNotIn("source_snapshot", script)
        self.assertNotIn("$bin/python", script)
        self.assertNotIn("--exclude='./legacy'", script)
        self.assertNotIn("-m playwright install chromium", script)
        self.assertIn("Creating macOS tar.gz archive", script)
        self.assertIn("-m paper_fetch.formula.install", script)
        self.assertIn("--no-node", script)
        self.assertIn("TEXMATH_VERSION", script)
        self.assertIn('"$texmath_bin" --version', script)
        self.assertIn(r"\frac{x_{1}}{\sqrt{y + 1}}", script)
        self.assertIn(r"\sum\limits_{i}^{n}x^{i}", script)
        self.assertIn('"$npm_bin" ci --omit=dev --silent', script)
        self.assertIn("mathml_to_latex_cli.mjs", script)
        self.assertNotIn(
            "paper-fetch bundled MathML-to-LaTeX compatibility launcher", script
        )

    def test_posix_manifest_and_readme_document_browser_backend_policy(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        manifest_block = script[
            script.index("payload = {") : script.index(
                '(staging / "offline-manifest.json")'
            )
        ]

        self.assertIn('"schema_version": 3', manifest_block)
        self.assertIn('"skill_bundle": skill_bundle', manifest_block)
        self.assertIn('"python_runtime": "runtime/site-packages"', manifest_block)
        self.assertIn('"command_wrappers": "bin"', manifest_block)
        self.assertIn('"camoufox"', manifest_block)
        self.assertIn('"camoufox"', manifest_block)
        self.assertIn('"browser_binary": "not_bundled"', manifest_block)
        self.assertIn('"platform": target_platform', manifest_block)
        self.assertIn('"arch": target_arch', manifest_block)
        self.assertIn("README.offline.md", script)
        self.assertIn("PAPER_FETCH_BROWSER_HEADLESS=false", script)
        self.assertNotIn("CLOAKBROWSER_", script)
        self.assertNotIn("PAPER_FETCH_BROWSER_USER_AGENT", script)
        self.assertNotIn('"source_snapshot"', manifest_block)
        self.assertNotIn('"wheelhouse_count"', manifest_block)
        self.assertIn("macos_offline_name_prefix", script)
        self.assertNotIn('"playwright_browsers"', manifest_block)

    def test_macos_build_contract_declares_arm64_minimum_os_and_relocatable_formula_bundle(
        self,
    ) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        target_block = script[
            script.index("check_target()") : script.index("project_version()")
        ]
        formula_block = script[
            script.index("copy_macos_library_licenses()") : script.index(
                "bundle_image_tools()"
            )
        ]
        manifest_block = script[
            script.index("write_manifest_and_checksums()") : script.index(
                "create_self_extracting_installer()"
            )
        ]

        self.assertIn('MACOS_MINIMUM_OS_VERSION="15.0"', script)
        self.assertIn("macos:arm64", target_block)
        self.assertIn("detect_python_arch", target_block)
        self.assertIn("standard GIL CPython", target_block)
        self.assertIn('sysconfig.get_config_var("Py_GIL_DISABLED")', script)
        self.assertIn('"SOABI"', script)
        self.assertIn(
            "does not match the target host architecture",
            target_block,
        )
        self.assertIn(
            "Offline macOS package build currently targets Apple Silicon arm64 only",
            target_block,
        )
        for tag in ("cp311", "cp312", "cp313", "cp314"):
            self.assertIn(tag, script)
        self.assertIn(
            'export MACOSX_DEPLOYMENT_TARGET="$target_minimum_os_version"',
            script,
        )
        self.assertIn('"minimum_os_version"', manifest_block)
        self.assertIn("minimum_os_version = sys.argv[7] or None", manifest_block)
        self.assertIn("stage_macos_formula_library", formula_block)
        self.assertIn("otool -L", formula_block)
        self.assertIn('install_name_tool -id "@rpath/$name"', formula_block)
        self.assertIn(
            'install_name_tool -change "$child" "@loader_path/$child_name"',
            formula_block,
        )
        self.assertIn(
            'install_name_tool -change "$dependency" "@loader_path/../lib/$name"',
            formula_block,
        )
        self.assertIn(
            'codesign --force --sign - --timestamp=none "$texmath"',
            formula_block,
        )
        self.assertIn("sign_macos_playwright_node", script)
        self.assertIn('file -b "$path"', script)
        self.assertIn('lipo -archs "$path"', script)
        self.assertIn(
            'codesign --force --sign - --timestamp=none "$playwright_node"',
            script,
        )
        self.assertIn('codesign --verify --strict "$playwright_node"', script)
        self.assertLess(
            script.index('sign_macos_playwright_node "$staging" "$target_platform"'),
            script.index('write_manifest_and_checksums \\\n    "$staging"'),
        )

    def test_macos_offline_verifier_uses_zsh_and_native_formula_checks(
        self,
    ) -> None:
        script = VERIFY_OFFLINE_PACKAGE.read_text(encoding="utf-8")

        self.assertIn('VERIFY_SHELL="/bin/zsh"', script)
        self.assertIn('SHELL_STARTUP_NAME=".zshrc"', script)
        self.assertIn("Verifying activation from native Zsh", script)
        self.assertIn('"$VERIFY_SHELL" -f -c', script)
        self.assertIn("verify_macos_native_bundle", script)
        self.assertIn('file -b "$path"', script)
        self.assertIn('lipo -archs "$path"', script)
        self.assertIn('otool -L "$canonical"', script)
        self.assertIn('codesign --verify --strict "$path"', script)
        self.assertIn("non-relocatable dependency", script)
        self.assertIn("macos_contained_path", script)
        self.assertIn("macos_rpaths", script)
        self.assertIn("LC_RPATH", script)
        self.assertIn("MACHO_VISITED_FILE", script)
        self.assertIn("verify_macos_macho_dependencies", script)
        self.assertIn('"$node" --version', script)
        self.assertIn("Playwright Node runtime failed to launch", script)
        self.assertLess(
            script.index("check_macos_bundle_quarantine"),
            script.index("verify_macos_native_bundle\n"),
        )
        self.assertIn(
            "grep -E -q ': com\\.apple\\.quarantine$' <<< \"$quarantine_output\"",
            script,
        )
        self.assertIn("Verifying recursive macOS quarantine rejection", script)
        self.assertIn("xattr -w com.apple.quarantine", script)
        self.assertIn('ln -s "config/zshrc"', script)
        self.assertIn('INSTALL_USER_CONFIG_FLAG="--user-config"', script)

    def test_posix_checksums_are_portable_to_macos(self) -> None:
        script = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8") + (
            REPO_ROOT / "install-offline.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("shasum -a 256", script)
        self.assertIn("sha256sum", script)
        self.assertNotIn('sed -i "s|__CLOAKBROWSER_HEADLESS__', script)
        self.assertNotIn("sed -i", script)

    def test_posix_offline_verifier_uses_browser_runtime_smoke(self) -> None:
        script = VERIFY_OFFLINE_PACKAGE.read_text(encoding="utf-8")

        self.assertIn("offline-installer.sh|offline-bundle.tar.gz", script)
        self.assertIn("extract_offline_archive_safely", script)
        self.assertNotIn("tar -xzf", script)
        self.assertIn('bundle.extractall(destination, filter="data")', script)
        self.assertIn("--archive-preflight-only", script)
        self.assertIn("INSTALLER_PATH", script)
        self.assertIn('--install-dir "$INSTALL_ROOT"', script)
        self.assertIn("runtime/site-packages/paper_fetch", script)
        self.assertIn("Offline install should not include the source tree", script)
        self.assertIn(
            "Offline install should not expose a generic Python wrapper", script
        )
        self.assertIn("Offline install should not include the build wheelhouse", script)
        self.assertIn("Purge did not remove the install directory", script)
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
        self.assertIn("PAPER_FETCH_BROWSER_HEADLESS=true", script)
        self.assertIn("Antigravity skill was not installed", script)
        self.assertIn("mcp_config.json", script)
        self.assertIn("activate-offline.sh executed shell code", script)
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", script)
        self.assertIn('texmath --version 2>&1)" = "Version 0.13.2"', script)
        self.assertIn(r"\frac{x_{1}}{\sqrt{y + 1}}", script)
        self.assertIn(r"\sum\limits_{i}^{n}x^{i}", script)
        self.assertIn("PYTHONUTF8", script)
        self.assertIn("PYTHONIOENCODING", script)
        self.assertIn('paper-fetch fetch --query "10.1186/1471-2105-11-421"', script)
        self.assertNotIn('paper-fetch --query "10.1186/1471-2105-11-421"', script)
        self.assertIn("paper-fetch doctor", script)
        self.assertIn("scripts/skill_integrity.py", script)
        self.assertNotIn(".venv/bin", script)
        self.assertNotIn("sessions.list", script)
        self.assertNotIn("playwright.sync_api", script)

    def test_windows_package_build_creates_runtime_only_staging(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")

        self.assertIn("$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)", script)
        self.assertIn("Copy-RuntimeAssets", script)
        self.assertIn("windows-runtime-wheelhouse", script)
        self.assertIn("runtime/Lib/site-packages", script)
        self.assertIn("Assert-RuntimeOnlyStaging", script)
        self.assertIn("scripts/windows-installer-helper.ps1", script)
        self.assertIn("installer/manifest.json", script)
        self.assertIn(
            '$sourceSkill = Join-Path (Join-Path $RepoDir "skills") $SkillName', script
        )
        self.assertIn(
            'Get-ChildItem -Path $wheelhouse -Filter "camoufox-*.whl"', script
        )
        self.assertIn(
            'Get-ChildItem -Path $wheelhouse -Filter "camoufox-*.whl"', script
        )
        self.assertIn('browser_binary = "not_bundled"', script)
        self.assertIn("Write-OfflineReadme", script)
        self.assertIn("skill_integrity.py", script)
        self.assertIn("skill_bundle = $skillBundle", script)
        self.assertNotIn("Copy-SourceSnapshot", script)
        self.assertNotIn("robocopy", script)
        self.assertNotIn('Join-Path $RepoDir "legacy"', script)
        self.assertNotIn('Join-Path $Staging "wheelhouse"', script)
        self.assertNotIn('Join-Path $Staging "dist"', script)
        self.assertNotIn("Add-PlaywrightChromium", script)
        self.assertNotIn("-m playwright install chromium", script)
        self.assertIn("TEXMATH_VERSION", script)
        self.assertIn("texmath --version", script)
        self.assertIn(r"\frac{x_{1}}{\sqrt{y + 1}}", script)
        self.assertIn(r"\sum\limits_{i}^{n}x^{i}", script)
        self.assertIn("npm ci --omit=dev --silent --prefix", script)
        self.assertIn("mathml_to_latex_cli.mjs", script)

    def test_windows_embedded_runtime_is_manifest_pinned_and_verified_before_extract(
        self,
    ) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")
        manifest = json.loads(
            (REPO_ROOT / "installer" / "manifest.json").read_text(encoding="utf-8")
        )
        runtime = manifest["embedded_runtimes"]["windows_cpython_x86_64"]

        self.assertEqual(runtime["version"], "3.13.13")
        self.assertEqual(
            runtime["url"],
            "https://www.python.org/ftp/python/3.13.13/python-3.13.13-embed-amd64.zip",
        )
        self.assertEqual(
            runtime["sha256"],
            "8766a8775746235e23cf5aee5027ab1060bb981d93110577adcf3508aa0cbd55",
        )
        self.assertNotIn("[string]$EmbeddedPythonVersion", script)
        digest_check = script.index("CPython embeddable archive SHA-256 mismatch")
        extraction = script.index("Expand-Archive -LiteralPath $archive")
        self.assertLess(digest_check, extraction)
        self.assertIn("expected_sha256 = $EmbeddedPythonSha256", script)
        self.assertIn("actual_sha256 = $EmbeddedPythonActualSha256", script)

    def test_windows_uninsis_is_manifest_pinned_verified_and_evidenced(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")
        manifest = json.loads(
            (REPO_ROOT / "installer" / "manifest.json").read_text(encoding="utf-8")
        )
        component = manifest["setup_components"]["windows_uninsis_i386"]

        self.assertEqual(component["version"], "1.7.0")
        self.assertEqual(component["architecture"], "i386")
        self.assertEqual(
            component["dll_sha256"],
            "9bf8badad59783459f85a1e6203f0c8257bb9554927ca2fa6df5f74850bdcf78",
        )
        self.assertEqual(component["license"], "LGPL-3.0-or-later")
        digest_check = script.index("UninsIS DLL SHA-256 mismatch")
        compile_call = script.index("Build-InnoInstaller -Staging $staging")
        self.assertLess(digest_check, compile_call)
        self.assertIn("Get-VerifiedUninsISDigests", script)
        self.assertIn("UninsIS license SHA-256 mismatch", script)
        self.assertIn("setup_components = [ordered]@{", script)
        self.assertIn("expected_sha256 = $UninsISDllSha256", script)
        self.assertIn("actual_sha256 = $UninsISActualSha256", script)

    def test_offline_builders_emit_actual_target_dependency_evidence(self) -> None:
        posix = BUILD_OFFLINE_PACKAGE.read_text(encoding="utf-8")
        windows = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")

        for script in (posix, windows):
            self.assertIn("generate_offline_evidence.py", script)
            self.assertIn("dependency-manifest.json", script)
            self.assertIn("paper-fetch-sbom.cdx.json", script)
            self.assertIn("paper-fetch-evidence-", script)
        self.assertIn('site-packages "$staging/runtime/site-packages"', posix)
        self.assertIn('Join-Path $Staging "runtime/Lib/site-packages"', windows)

    def test_windows_wrappers_and_manifest_publish_browser_backend_policy(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")
        wrapper_block = script[
            script.index("function Write-CmdWrappers") : script.index(
                "function Write-DefaultOfflineEnv"
            )
        ]
        manifest_block = script[
            script.index("components = [ordered]@{") : script.index(
                "installer = [ordered]@{"
            )
        ]

        self.assertIn("paper-fetch.cmd", wrapper_block)
        self.assertIn("paper-fetch-mcp.cmd", wrapper_block)
        self.assertIn('command_wrappers = "bin"', manifest_block)
        self.assertIn("camoufox = [ordered]@{", manifest_block)
        self.assertIn("camoufox = [ordered]@{", manifest_block)
        self.assertIn("$OfflineEnvKeys", script)
        self.assertIn("$InstallerManifest.mcp.env_keys", script)
        self.assertIn('Where-Object { $_ -ne "PAPER_FETCH_ENV_FILE" }', script)
        self.assertIn("Get-DefaultOfflineEnvValue", script)
        self.assertIn("PAPER_FETCH_BROWSER_HEADLESS", script)
        self.assertNotIn("CLOAKBROWSER_", script)
        self.assertNotIn("PAPER_FETCH_BROWSER_USER_AGENT", script)
        self.assertNotIn("project_wheels", manifest_block)
        self.assertNotIn("wheelhouse_count", manifest_block)
        self.assertNotIn("source_snapshot", manifest_block)
        self.assertNotIn("inno_setup", manifest_block)
        self.assertNotIn("playwright_browsers", manifest_block)

    def test_windows_powershell_here_string_terminators_are_flush_left(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")

        for line_number, line in enumerate(script.splitlines(), start=1):
            if line.strip() in {"'@", '"@'}:
                self.assertEqual(
                    line,
                    line.strip(),
                    f"PowerShell here-string terminator must be flush-left at line {line_number}",
                )

    def test_windows_powershell_arrays_do_not_end_with_trailing_commas(self) -> None:
        paths = (
            REPO_ROOT / "scripts" / "build-offline-package-windows.ps1",
            REPO_ROOT / "scripts" / "windows-installer-helper.ps1",
        )

        for path in paths:
            script = path.read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r",\s*\)", script),
                f"PowerShell trailing comma before ')' in {path.relative_to(REPO_ROOT)}",
            )


if __name__ == "__main__":
    unittest.main()
