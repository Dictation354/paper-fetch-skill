from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
LINUX_OFFLINE_VERIFY = REPO_ROOT / "scripts" / "verify-offline-package.sh"
DEV_PREFLIGHT = REPO_ROOT / "scripts" / "dev-preflight.sh"
PYPROJECT = REPO_ROOT / "pyproject.toml"
OFFLINE_JOB_IDS = (
    "offline-linux-x86-64",
    "offline-macos-install",
    "offline-windows-x86-64",
)
OFFLINE_NON_WINDOWS_IF = "${{ (startsWith(github.ref, 'refs/tags/v') || github.event_name == 'workflow_dispatch') && (github.event_name != 'workflow_dispatch' || !inputs.run_offline_windows_only) }}"
OFFLINE_WINDOWS_IF = "${{ startsWith(github.ref, 'refs/tags/v') || github.event_name == 'workflow_dispatch' }}"


def _load_ci_workflow() -> dict:
    workflow = yaml.load(
        CI_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    if not isinstance(workflow, dict):
        raise AssertionError("CI workflow did not parse to a mapping")
    return workflow


def _job_if(workflow: dict, job_id: str) -> str:
    job = workflow["jobs"][job_id]
    condition = job.get("if", "")
    if not isinstance(condition, str):
        raise AssertionError(f"{job_id} has non-string if condition: {condition!r}")
    return condition


def _evaluate_github_if(
    expression: str,
    *,
    event_name: str,
    ref: str,
    run_offline_windows_only: bool = False,
    publish_release: bool = False,
) -> bool:
    expr = expression.strip()
    if expr.startswith("${{") and expr.endswith("}}"):
        expr = expr[3:-2]
    expr = re.sub(r"\s+", " ", expr).strip()
    expr = expr.replace(
        "startsWith(github.ref, 'refs/tags/v')",
        "ref.startswith('refs/tags/v')",
    )
    expr = expr.replace("github.event_name", "event_name")
    expr = expr.replace("inputs.run_offline_windows_only", "run_offline_windows_only")
    expr = expr.replace("inputs.publish_release", "publish_release")
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"!\s*(?!=)", " not ", expr)
    return bool(
        eval(  # noqa: S307 - test-only evaluator for the workflow expression subset.
            expr,
            {"__builtins__": {}},
            {
                "event_name": event_name,
                "publish_release": publish_release,
                "ref": ref,
                "run_offline_windows_only": run_offline_windows_only,
            },
        )
    )


class CiReleaseWorkflowTests(unittest.TestCase):
    def test_phase8_release_workflow_input_is_absent_in_this_repository(self) -> None:
        self.assertFalse(RELEASE_WORKFLOW.exists())
        self.assertTrue(CI_WORKFLOW.exists())

    def test_ci_workflow_declares_regular_and_manual_triggers(self) -> None:
        workflow = _load_ci_workflow()

        self.assertEqual(
            {"pull_request", "push", "workflow_dispatch"},
            set(workflow["on"]),
        )
        dispatch_inputs = workflow["on"]["workflow_dispatch"]["inputs"]
        self.assertIn("publish_release", dispatch_inputs)
        self.assertIn("run_offline_windows_only", dispatch_inputs)

    def test_offline_jobs_only_run_on_tags_or_manual_dispatch(self) -> None:
        workflow = _load_ci_workflow()
        expected_conditions = {
            "offline-linux-x86-64": OFFLINE_NON_WINDOWS_IF,
            "offline-macos-install": OFFLINE_NON_WINDOWS_IF,
            "offline-windows-x86-64": OFFLINE_WINDOWS_IF,
        }

        for job_id, expected_condition in expected_conditions.items():
            with self.subTest(job_id=job_id):
                condition = _job_if(workflow, job_id)

                self.assertEqual(expected_condition, condition)
                self.assertFalse(
                    _evaluate_github_if(
                        condition,
                        event_name="push",
                        ref="refs/heads/main",
                    )
                )
                self.assertFalse(
                    _evaluate_github_if(
                        condition,
                        event_name="pull_request",
                        ref="refs/pull/1/merge",
                    )
                )
                self.assertTrue(
                    _evaluate_github_if(
                        condition,
                        event_name="push",
                        ref="refs/tags/v3.0.0",
                    )
                )
                self.assertTrue(
                    _evaluate_github_if(
                        condition,
                        event_name="workflow_dispatch",
                        ref="refs/heads/main",
                    )
                )

        self.assertFalse(
            _evaluate_github_if(
                _job_if(workflow, "offline-linux-x86-64"),
                event_name="workflow_dispatch",
                ref="refs/heads/main",
                run_offline_windows_only=True,
            )
        )
        self.assertFalse(
            _evaluate_github_if(
                _job_if(workflow, "offline-macos-install"),
                event_name="workflow_dispatch",
                ref="refs/heads/main",
                run_offline_windows_only=True,
            )
        )
        self.assertTrue(
            _evaluate_github_if(
                _job_if(workflow, "offline-windows-x86-64"),
                event_name="workflow_dispatch",
                ref="refs/heads/main",
                run_offline_windows_only=True,
            )
        )

    def test_package_smoke_remains_a_regular_quality_gate(self) -> None:
        workflow = _load_ci_workflow()
        condition = _job_if(workflow, "package-smoke")

        self.assertTrue(
            _evaluate_github_if(condition, event_name="push", ref="refs/heads/main")
        )
        self.assertTrue(
            _evaluate_github_if(
                condition,
                event_name="pull_request",
                ref="refs/pull/1/merge",
            )
        )
        self.assertTrue(
            _evaluate_github_if(
                condition,
                event_name="workflow_dispatch",
                ref="refs/heads/main",
            )
        )
        self.assertFalse(
            _evaluate_github_if(
                condition,
                event_name="workflow_dispatch",
                ref="refs/heads/main",
                run_offline_windows_only=True,
            )
        )

    def test_release_job_requires_v_tag_and_release_intent(self) -> None:
        workflow = _load_ci_workflow()
        release_job = workflow["jobs"]["release-offline-packages"]
        condition = _job_if(workflow, "release-offline-packages")

        self.assertTrue(
            {"package-smoke", *OFFLINE_JOB_IDS}.issubset(release_job["needs"])
        )
        self.assertFalse(
            _evaluate_github_if(condition, event_name="push", ref="refs/heads/main")
        )
        self.assertFalse(
            _evaluate_github_if(
                condition,
                event_name="pull_request",
                ref="refs/tags/v3.0.0",
            )
        )
        self.assertTrue(
            _evaluate_github_if(condition, event_name="push", ref="refs/tags/v3.0.0")
        )
        self.assertFalse(
            _evaluate_github_if(
                condition,
                event_name="workflow_dispatch",
                ref="refs/heads/main",
                publish_release=True,
            )
        )
        self.assertFalse(
            _evaluate_github_if(
                condition,
                event_name="workflow_dispatch",
                ref="refs/tags/v3.0.0",
            )
        )
        self.assertTrue(
            _evaluate_github_if(
                condition,
                event_name="workflow_dispatch",
                ref="refs/tags/v3.0.0",
                publish_release=True,
            )
        )
        self.assertFalse(
            _evaluate_github_if(
                condition,
                event_name="workflow_dispatch",
                ref="refs/tags/v3.0.0",
                publish_release=True,
                run_offline_windows_only=True,
            )
        )

    def test_release_notes_come_from_chinese_changelog(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Extract release notes from CHANGELOG_CN", workflow)
        self.assertIn("CHANGELOG_CN.md > release-notes.md", workflow)
        self.assertIn("body_path: release-notes.md", workflow)
        self.assertIn("generate_release_notes: false", workflow)

    def test_ci_and_local_preflight_share_core_quality_gates(self) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        preflight = DEV_PREFLIGHT.read_text(encoding="utf-8")

        self.assertIn("python -m mypy", workflow)
        self.assertIn("python -m ruff format --check .", workflow)
        self.assertIn("--cov=paper_fetch", workflow)
        self.assertIn("--cov-report=term-missing", workflow)
        self.assertIn("--cov-report=xml", workflow)
        self.assertIn("--cov-fail-under=40", workflow)
        self.assertIn("bash scripts/dev-preflight.sh --help", workflow)
        self.assertIn("PYTHON_BIN", preflight)
        self.assertIn("-m mypy", preflight)
        self.assertNotIn("--no-site-packages", preflight)
        self.assertIn("-m ruff format --check .", preflight)
        self.assertIn("-m ruff check .", preflight)
        self.assertIn("--coverage", preflight)
        self.assertIn("--cov=paper_fetch", preflight)
        self.assertIn("--cov-fail-under=40", preflight)
        self.assertIn("tests/unit -q", preflight)
        self.assertIn("tests/unit -q --durations=30", preflight)
        self.assertIn("tests/devtools -q", preflight)
        self.assertIn("scripts/validate_extraction_rules.py", preflight)
        self.assertIn("scripts/validate_extraction_rules.py --ci", preflight)
        self.assertIn("tests/integration -q", preflight)
        self.assertIn("--durations=30", workflow)

    def test_quality_gate_config_guards_mypy_coverage_and_b023(self) -> None:
        with PYPROJECT.open("rb") as handle:
            pyproject = tomllib.load(handle)

        mypy_config = pyproject["tool"]["mypy"]
        mypy_files = set(mypy_config["files"])
        self.assertTrue(mypy_config["no_site_packages"])
        self.assertGreaterEqual(
            pyproject["tool"]["coverage"]["report"]["fail_under"], 40
        )
        self.assertEqual(
            pyproject["tool"]["ruff"]["lint"].get("per-file-ignores", {}), {}
        )
        for entry in mypy_files:
            path = REPO_ROOT / entry
            self.assertTrue(path.exists(), f"mypy files entry does not exist: {entry}")
            if path.is_dir():
                self.assertTrue(
                    any(path.rglob("*.py")) or any(path.rglob("*.pyi")),
                    f"mypy directory entry has no Python files: {entry}",
                )

        required_mypy_paths = {
            "src/paper_fetch/_cloakbrowser_runtime.py",
            "src/paper_fetch/config.py",
            "src/paper_fetch/runtime.py",
            "src/paper_fetch/runtime_browser.py",
            "src/paper_fetch/formula/convert.py",
            "src/paper_fetch/formula/paths.py",
            "src/paper_fetch/quality",
            "src/paper_fetch/providers/_waterfall.py",
            "src/paper_fetch/providers/_pdf_common.py",
            "src/paper_fetch/providers/_pdf_fallback.py",
            "src/paper_fetch/providers/browser_runtime",
            "src/paper_fetch/providers/browser_workflow",
        }
        self.assertLessEqual(required_mypy_paths, mypy_files)

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
