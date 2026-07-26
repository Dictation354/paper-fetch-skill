from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "build-offline-package.sh"
BUILD_OFFLINE_PACKAGE_WINDOWS = (
    REPO_ROOT / "scripts" / "build-offline-package-windows.ps1"
)
VERIFY_OFFLINE_PACKAGE = REPO_ROOT / "scripts" / "verify-offline-package.sh"


class OfflinePackageBuildTests(unittest.TestCase):
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
        self.assertIn("camoufox-*.whl", script)
        self.assertIn("Dependency wheelhouse is missing camoufox-*.whl", script)
        self.assertIn("-m compileall", script)
        self.assertNotIn("copy_source_snapshot", script)
        self.assertNotIn("source_snapshot", script)
        self.assertNotIn("$bin/python", script)
        self.assertNotIn("--exclude='./legacy'", script)
        self.assertNotIn("-m playwright install chromium", script)
        self.assertIn("Creating macOS tar.gz archive", script)
        self.assertIn('"$npm_bin" ci --omit=dev --silent', script)
        self.assertIn("mathml_to_latex_cli.mjs", script)
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", script)
        self.assertNotIn("--no-node", script)

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
        self.assertIn("tar -xzf", script)
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
            "from paper_fetch.runtime_browser import BrowserContextManager", script
        )
        self.assertIn('assert hasattr(camoufox, "Camoufox")', script)
        self.assertNotIn('assert hasattr(camoufox, "launch")', script)
        self.assertIn("PAPER_FETCH_BROWSER_HEADLESS=true", script)
        self.assertIn("Antigravity skill was not installed", script)
        self.assertIn("mcp_config.json", script)
        self.assertIn("activate-offline.sh executed shell code", script)
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", script)
        self.assertIn("<math><mi>x</mi></math>", script)
        self.assertIn("PYTHONUTF8", script)
        self.assertIn("PYTHONIOENCODING", script)
        self.assertIn("paper-fetch doctor", script)
        self.assertIn("install_provenance", script)
        self.assertIn('schema_version"] == 3', script)
        self.assertNotIn(".venv/bin", script)
        self.assertNotIn("sessions.list", script)
        self.assertNotIn("playwright.sync_api", script)

    def test_windows_package_build_creates_runtime_only_staging(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")

        self.assertIn(
            "$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)", script
        )
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

    def test_windows_wrappers_and_manifest_publish_browser_backend_policy(self) -> None:
        script = BUILD_OFFLINE_PACKAGE_WINDOWS.read_text(encoding="utf-8")
        wrapper_block = script[
            script.index("function Write-CmdWrappers") : script.index(
                "function Add-SkillAgentManifest"
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
        self.assertIn("env_sets.offline_env_keys", script)
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
            REPO_ROOT / "install-offline.ps1",
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
