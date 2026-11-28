from __future__ import annotations

import json
import unittest
from pathlib import Path

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
            "from paper_fetch.providers.browser_runtime.preparation import "
            "verify_package_installation",
            linux_script,
        )

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
        self.assertIn('Type: files; Name: "{app}\\browser-setup-results.txt"', script)
        self.assertNotIn("fpgen", script)
        self.assertIn('-LogPath "', script)
        self.assertIn('" -Action Install', script)
        self.assertIn("RestoreOfflineEnv;\n    RunPostInstallHelper;", script)
        self.assertIn("RunPostInstallHelper;\n    PrepareBrowsers;", script)
        self.assertIn("--prepare-browsers --non-interactive --result", script)
        self.assertIn("browser-setup-results.txt", script)
        self.assertIn("Browser preparation: ready", script)
        self.assertIn("Browser preparation: not ready", script)
        self.assertIn("Browser preparation: skipped", script)
        self.assertNotIn("Pos('Byparr: ready'", script)
        self.assertNotIn("OptionalBrowser", script)
        self.assertIn("Lines[2] := '0';", script)
        preparation = script.split("procedure PrepareBrowsers;", 1)[1].split(
            "function PrepareToInstall", 1
        )[0]
        self.assertLess(
            preparation.index("DeleteFile(ResultPath)"),
            preparation.index("if SkipBrowserPrepare"),
        )
        self.assertIn("if ResultCode = 0 then", preparation)
        self.assertNotIn("CheckSystemChrome", script)
        self.assertNotIn(
            "Paper Fetch Skill post-install helper failed with exit code", script
        )

    def test_installer_manifest_has_one_canonical_runtime_env_set(self) -> None:
        manifest = json.loads(
            (REPO_ROOT / "installer" / "manifest.json").read_text(encoding="utf-8")
        )

        mcp_env_keys = manifest["runtime"]["env_keys"]
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["skill"], {"name": "paper-fetch-skill"})
        self.assertNotIn("env_sets", manifest)
        self.assertIn("MATHML_TO_LATEX_NODE_BIN", mcp_env_keys)
        self.assertIn("PAPER_FETCH_IMAGE_TOOLS_DIR", mcp_env_keys)
        installer = LINUX_INSTALLER.read_text(encoding="utf-8")
        self.assertIn('SHELL_ENV_KEYS=("${RUNTIME_ENV_KEYS[@]}")', installer)
        self.assertIn('ACTIVATE_ENV_KEYS=("${RUNTIME_ENV_KEYS[@]}")', installer)
        self.assertIn('[ "$key" != "PAPER_FETCH_ENV_FILE" ]', installer)

    def test_windows_offline_build_writes_default_mathml_node_env(self) -> None:
        script = WINDOWS_OFFLINE_BUILD.read_text(encoding="utf-8")

        self.assertIn("MATHML_TO_LATEX_NODE_BIN", script)
        self.assertIn("PAPER_FETCH_IMAGE_TOOLS_DIR", script)
        self.assertIn("--offline-bundle", script)
        self.assertIn("--repo-root", script)
        self.assertIn("runtime/node/node.exe", script)
        self.assertIn("PLAYWRIGHT_NODEJS_PATH", script)

    def test_linux_offline_build_uses_image_tools_offline_bundle_mode(self) -> None:
        script = LINUX_OFFLINE_BUILD.read_text(encoding="utf-8")

        self.assertIn("-m paper_fetch.image_tools.install", script)
        self.assertIn("--offline-bundle", script)
        self.assertIn('--repo-root "$REPO_DIR"', script)

    def test_offline_cli_launcher_prepends_bundled_tool_paths(self) -> None:
        script = LINUX_OFFLINE_BUILD.read_text(encoding="utf-8")
        launcher = script.split('cat > "$bin/paper-fetch"', 1)[1].split("\nEOF", 1)[0]
        self.assertIn(
            'export PATH="$INSTALL_ROOT/bin:$INSTALL_ROOT/formula-tools/bin:'
            '$INSTALL_ROOT/image-tools/bin${PATH:+:$PATH}"',
            launcher,
        )

    def test_offline_cli_reads_only_regular_default_env_binding(self) -> None:
        script = LINUX_OFFLINE_BUILD.read_text(encoding="utf-8")
        launcher = script.split('cat > "$bin/paper-fetch"', 1)[1].split("\nEOF", 1)[0]
        self.assertIn(
            'default_env_file="$INSTALL_ROOT/runtime/default-env-file"', launcher
        )
        self.assertIn(
            '[ -f "$default_env_file" ] && [ ! -L "$default_env_file" ]', launcher
        )
        self.assertIn("IFS= read -r PAPER_FETCH_ENV_FILE", launcher)

    def test_user_launcher_is_installed_after_validation_and_shell_integration(
        self,
    ) -> None:
        script = LINUX_INSTALLER.read_text(encoding="utf-8")
        main = script.split("main() {", 1)[1]
        launcher = main.index("\n  install_user_launcher\n")
        self.assertLess(main.index("\n  check_macos_quarantine\n"), launcher)
        self.assertLess(main.index("\n  install_runtime_payload\n"), launcher)
        self.assertIn("\n  write_shell_startup_file\n  install_user_launcher\n", main)
