from __future__ import annotations
import unittest
from pathlib import Path
import json


REPO_ROOT = Path(__file__).resolve().parents[2]

LINUX_INSTALLER = REPO_ROOT / "install-offline.sh"

WINDOWS_INSTALLER_HELPER = REPO_ROOT / "scripts" / "windows-installer-helper.ps1"

LINUX_OFFLINE_BUILD = REPO_ROOT / "scripts" / "build-offline-package.sh"

WINDOWS_OFFLINE_BUILD = REPO_ROOT / "scripts" / "build-offline-package-windows.ps1"

WINDOWS_INNO_INSTALLER = REPO_ROOT / "installer" / "paper-fetch-skill.iss"


if __name__ == "__main__":
    unittest.main()


class OfflineInstallTests(unittest.TestCase):
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
