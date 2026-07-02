from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
LINUX_OFFLINE_VERIFY = REPO_ROOT / "scripts" / "verify-offline-package.sh"
DEV_PREFLIGHT = REPO_ROOT / "scripts" / "dev-preflight.sh"


class CiReleaseWorkflowTests(unittest.TestCase):
    def test_phase8_release_workflow_input_is_absent_in_this_repository(self) -> None:
        self.assertFalse(RELEASE_WORKFLOW.exists())
        self.assertTrue(CI_WORKFLOW.exists())

    def test_ci_and_local_preflight_share_core_quality_gates(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        preflight = DEV_PREFLIGHT.read_text(encoding="utf-8")

        self.assertIn("python -m mypy", workflow)
        self.assertIn("python -m ruff format --check .", workflow)
        self.assertIn("--cov=paper_fetch", workflow)
        self.assertIn("--cov-report=term-missing", workflow)
        self.assertIn("--cov-report=xml", workflow)
        self.assertIn("bash scripts/dev-preflight.sh --help", workflow)
        self.assertIn("PYTHON_BIN", preflight)
        self.assertIn("-m mypy", preflight)
        self.assertIn("--no-site-packages", preflight)
        self.assertIn("-m ruff format --check .", preflight)
        self.assertIn("-m ruff check .", preflight)
        self.assertIn("--coverage", preflight)
        self.assertIn("--cov=paper_fetch", preflight)
        self.assertIn("tests/unit -q", preflight)
        self.assertIn("tests/devtools -q", preflight)
        self.assertIn("scripts/validate_extraction_rules.py", preflight)
        self.assertIn("tests/integration -q", preflight)
        self.assertIn("--durations=30", workflow)

    def test_windows_offline_ci_uses_current_provider_status_entrypoint(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            "from paper_fetch.mcp.fetch_tool import provider_status_payload", workflow
        )
        self.assertIn(
            "Invoke-RuntimePythonScript -Script $providerStatusCheck", workflow
        )
        self.assertNotIn('& $runtimePython -X utf8 -c "import paper_fetch', workflow)
        self.assertNotIn(
            "from paper_fetch.mcp.tools import provider_status_payload", workflow
        )

    def test_windows_offline_ci_uses_browser_runtime_package_smoke(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("import cloakbrowser", workflow)
        self.assertIn("import playwright", workflow)
        self.assertIn(
            "from paper_fetch.runtime_browser import BrowserContextManager", workflow
        )
        self.assertIn('assert hasattr(cloakbrowser, "ensure_binary")', workflow)
        self.assertIn(
            "Invoke-RuntimePythonScript -Script $browserRuntimeCheck", workflow
        )
        self.assertNotIn("& $runtimePython -X utf8 -c $cloakbrowserCheck", workflow)
        self.assertNotIn("playwright.sync_api", workflow)
        self.assertNotIn("ms-playwright", workflow)

    def test_windows_offline_ci_verifies_bundled_mathml_node(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("MATHML_TO_LATEX_NODE_BIN", workflow)
        self.assertIn("runtime/Lib/site-packages/playwright/driver/node.exe", workflow)
        self.assertIn("$mathmlNode --version", workflow)

    def test_offline_ci_verifies_default_browser_user_agent(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        linux_verify = LINUX_OFFLINE_VERIFY.read_text(encoding="utf-8")

        self.assertIn("PAPER_FETCH_BROWSER_USER_AGENT", workflow)
        self.assertIn(
            "offline.env managed block does not enable default browser UA", workflow
        )
        self.assertIn("PAPER_FETCH_BROWSER_USER_AGENT", linux_verify)
        self.assertIn("Offline install did not enable default browser UA", linux_verify)

    def test_linux_offline_ci_verifies_runtime_package_layout(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Verify Linux runtime package layout", workflow)
        self.assertIn(".sh", workflow)
        self.assertIn('--install-dir "$install_root"', workflow)
        self.assertIn("/runtime/site-packages/paper_fetch/__init__.py", workflow)
        self.assertIn("/bin/paper-fetch", workflow)
        self.assertIn("/bin/paper-fetch-install-formula-tools", workflow)
        self.assertIn(
            "Linux runtime package must not include source/build path", workflow
        )
        self.assertNotIn("tar -tzf", workflow)
        self.assertNotIn(
            "paper-fetch-skill-offline-linux-x86_64-${{ matrix.python-tag }}.tar.gz",
            workflow,
        )

    def test_macos_offline_ci_verifies_headful_install_layout_and_uploads_release_asset(
        self,
    ) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("offline-macos-install:", workflow)
        self.assertIn("runs-on: macos-latest", workflow)
        for python_version, python_tag in (
            ("3.11", "cp311"),
            ("3.12", "cp312"),
            ("3.13", "cp313"),
            ("3.14", "cp314"),
        ):
            self.assertIn(f'python-version: "{python_version}"', workflow)
            self.assertIn(f'python-tag: "{python_tag}"', workflow)
        self.assertIn("Build macOS offline package", workflow)
        self.assertIn(
            "paper-fetch-skill-offline-macos-$package_arch-${{ matrix.python-tag }}.tar.gz",
            workflow,
        )
        self.assertIn("--preset=headful", workflow)
        self.assertIn(
            'CLOAKBROWSER_CDP_ENDPOINT="ws://127.0.0.1:9222/devtools/browser/..."',
            workflow,
        )
        self.assertIn('CLOAKBROWSER_HEADLESS="false"', workflow)
        self.assertIn(
            "macOS runtime package must not include source/build path", workflow
        )
        self.assertIn("- offline-macos-install", workflow)
        self.assertIn("Upload macOS offline package", workflow)
        self.assertIn(
            "name: paper-fetch-skill-offline-macos-${{ matrix.python-tag }}", workflow
        )
        self.assertIn(
            "path: offline-artifacts/paper-fetch-skill-offline-macos-*-${{ matrix.python-tag }}.tar.gz",
            workflow,
        )

    def test_release_asset_set_includes_one_macos_tarball_for_each_python_tag(
        self,
    ) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("python_tags=(cp311 cp312 cp313 cp314)", workflow)
        self.assertIn(
            'macos_assets=(release-artifacts/paper-fetch-skill-offline-macos-*-"$python_tag".tar.gz)',
            workflow,
        )
        self.assertIn("Expected exactly one macOS $python_tag release asset", workflow)
        self.assertIn(
            "paper-fetch-skill-offline-macos-arm64-$python_tag.tar.gz", workflow
        )
        self.assertIn(
            "paper-fetch-skill-offline-macos-x86_64-$python_tag.tar.gz", workflow
        )
        self.assertIn(
            'expected_count="$((${#expected[@]} + macos_asset_count))"', workflow
        )
        self.assertIn("Expected $expected_count release assets", workflow)

    def test_macos_offline_ci_runs_installed_package_browser_smoke(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Verify macOS installed package browser smoke", workflow)
        self.assertIn('PAPER_FETCH_BROWSER_BINARY="$browser_binary"', workflow)
        self.assertIn(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", workflow
        )
        self.assertIn('source "$install_root/activate-offline.sh"', workflow)
        self.assertIn("paper-fetch --help >/dev/null", workflow)
        self.assertIn(
            "from paper_fetch.runtime_browser import BrowserContextManager", workflow
        )
        self.assertIn("--remote-debugging-port", workflow)
        self.assertIn("CLOAKBROWSER_CDP_ENDPOINT", workflow)
        self.assertIn("BrowserContextManager(cdp_endpoint=endpoint)", workflow)
        self.assertIn(
            "data:text/html,<title>paper-fetch macOS browser smoke</title>", workflow
        )
        self.assertIn("\n          from pathlib import Path\n", workflow)
        self.assertIn(
            "\n          PY\n\n      - name: Upload macOS offline package", workflow
        )
        self.assertNotIn("\nfrom pathlib import Path\n", workflow)

    def test_windows_offline_ci_verifies_runtime_only_package_layout(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Windows installer is missing runtime path", workflow)
        self.assertIn("runtime/Lib/site-packages/paper_fetch/__init__.py", workflow)
        self.assertIn("bin/paper-fetch.cmd", workflow)
        self.assertIn("skills/paper-fetch-skill/SKILL.md", workflow)
        self.assertIn("scripts/windows-installer-helper.ps1", workflow)
        self.assertIn(
            "Windows runtime package must not include source/build path", workflow
        )
        self.assertIn("pyproject.toml", workflow)


if __name__ == "__main__":
    unittest.main()
