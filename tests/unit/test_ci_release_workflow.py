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
ROLLING_TARGETS = {
    "linux-x86_64-cp311",
    "linux-x86_64-cp312",
    "linux-x86_64-cp313",
    "linux-x86_64-cp314",
    "macos-arm64-cp311",
    "macos-arm64-cp312",
    "macos-arm64-cp313",
    "macos-arm64-cp314",
    "windows-x86_64-cp313",
}
ROLLING_ASSETS = {
    "SHA256SUMS",
    "dependency-manifest.json",
    "paper-fetch-skill-offline-linux-x86_64-cp311.sh",
    "paper-fetch-skill-offline-linux-x86_64-cp312.sh",
    "paper-fetch-skill-offline-linux-x86_64-cp313.sh",
    "paper-fetch-skill-offline-linux-x86_64-cp314.sh",
    "paper-fetch-skill-offline-macos-arm64-cp311.tar.gz",
    "paper-fetch-skill-offline-macos-arm64-cp312.tar.gz",
    "paper-fetch-skill-offline-macos-arm64-cp313.tar.gz",
    "paper-fetch-skill-offline-macos-arm64-cp314.tar.gz",
    "paper-fetch-skill-windows-x86_64-setup.exe",
}


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
    force_refresh: bool = False,
    dependency_refresh_result: str = "skipped",
    dependency_changed: bool = False,
) -> bool:
    expr = expression.strip()
    if expr.startswith("${{") and expr.endswith("}}"):
        expr = expr[3:-2]
    expr = re.sub(r"\s+", " ", expr).strip()
    expr = expr.replace(
        "startsWith(github.ref, 'refs/tags/v')",
        "ref.startswith('refs/tags/v')",
    )
    expr = expr.replace("always()", "True")
    expr = expr.replace(
        "needs.dependency-refresh-compare.outputs.changed",
        "dependency_changed",
    )
    expr = expr.replace(
        "needs.dependency-refresh-compare.result",
        "dependency_refresh_result",
    )
    expr = expr.replace("github.event_name", "event_name")
    expr = expr.replace("inputs.run_offline_windows_only", "run_offline_windows_only")
    expr = expr.replace("inputs.publish_release", "publish_release")
    expr = expr.replace("inputs.force_refresh", "force_refresh")
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"!\s*(?!=)", " not ", expr)
    return bool(
        eval(  # noqa: S307 - test-only evaluator for the workflow expression subset.
            expr,
            {"__builtins__": {}},
            {
                "event_name": event_name,
                "force_refresh": force_refresh,
                "dependency_changed": str(dependency_changed).lower(),
                "dependency_refresh_result": dependency_refresh_result,
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

    def test_ci_workflow_declares_regular_daily_and_manual_triggers(self) -> None:
        workflow = _load_ci_workflow()

        self.assertEqual(
            {"pull_request", "push", "schedule", "workflow_dispatch"},
            set(workflow["on"]),
        )
        self.assertEqual("17 19 * * *", workflow["on"]["schedule"][0]["cron"])
        dispatch_inputs = workflow["on"]["workflow_dispatch"]["inputs"]
        self.assertIn("publish_release", dispatch_inputs)
        self.assertIn("run_offline_windows_only", dispatch_inputs)
        self.assertEqual("false", dispatch_inputs["force_refresh"]["default"])
        self.assertIn(
            "paper-fetch-dependency-latest",
            workflow["concurrency"]["group"],
        )
        self.assertEqual("false", workflow["concurrency"]["cancel-in-progress"])

    def test_offline_jobs_run_for_release_or_changed_dependency_refresh(self) -> None:
        workflow = _load_ci_workflow()

        for job_id in OFFLINE_JOB_IDS:
            with self.subTest(job_id=job_id):
                condition = _job_if(workflow, job_id)

                self.assertEqual(
                    "dependency-refresh-compare", workflow["jobs"][job_id]["needs"]
                )
                self.assertIn("always()", condition)
                self.assertIn("inputs.force_refresh", condition)
                self.assertIn(
                    "needs.dependency-refresh-compare.outputs.changed", condition
                )
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
                        condition,
                        event_name="schedule",
                        ref="refs/heads/main",
                        dependency_refresh_result="success",
                        dependency_changed=False,
                    )
                )
                self.assertTrue(
                    _evaluate_github_if(
                        condition,
                        event_name="schedule",
                        ref="refs/heads/main",
                        dependency_refresh_result="success",
                        dependency_changed=True,
                    )
                )
                self.assertTrue(
                    _evaluate_github_if(
                        condition,
                        event_name="workflow_dispatch",
                        ref="refs/heads/main",
                        force_refresh=True,
                        run_offline_windows_only=True,
                        dependency_refresh_result="success",
                        dependency_changed=True,
                    )
                )
                self.assertFalse(
                    _evaluate_github_if(
                        condition,
                        event_name="schedule",
                        ref="refs/heads/main",
                        dependency_refresh_result="failure",
                        dependency_changed=True,
                    )
                )
                self.assertTrue(
                    _evaluate_github_if(
                        condition,
                        event_name="workflow_dispatch",
                        ref="refs/heads/main",
                        force_refresh=True,
                        dependency_refresh_result="success",
                        dependency_changed=True,
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
                event_name="schedule",
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
        self.assertFalse(
            _evaluate_github_if(
                condition,
                event_name="workflow_dispatch",
                ref="refs/heads/main",
                force_refresh=True,
            )
        )

    def test_dependency_refresh_resolves_exact_matrix_from_latest_stable_release(
        self,
    ) -> None:
        workflow = _load_ci_workflow()
        workflow_text = CI_WORKFLOW.read_text(encoding="utf-8")
        context_job = workflow["jobs"]["dependency-refresh-context"]
        resolve_job = workflow["jobs"]["dependency-refresh-resolve"]
        target_matrix = {
            entry["target"] for entry in resolve_job["strategy"]["matrix"]["include"]
        }

        self.assertIn("github.event_name == 'schedule'", context_job["if"])
        self.assertIn("inputs.force_refresh", context_job["if"])
        self.assertIn("releases/latest", workflow_text)
        self.assertIn("Latest stable release tag must start with v", workflow_text)
        self.assertEqual(ROLLING_TARGETS, target_matrix)
        self.assertIn('"pip==26.1.2" "packaging==26.2"', workflow_text)
        self.assertIn("resolve_offline_dependencies.py resolve", workflow_text)
        self.assertIn("dependency-snapshot-${{ matrix.target }}", workflow_text)

    def test_dependency_refresh_compares_complete_manifest_before_building(
        self,
    ) -> None:
        workflow = _load_ci_workflow()
        workflow_text = CI_WORKFLOW.read_text(encoding="utf-8")
        compare_job = workflow["jobs"]["dependency-refresh-compare"]
        baseline_step = next(
            step
            for step in compare_job["steps"]
            if step.get("name") == "Download rolling release baseline"
        )
        baseline_script = baseline_step["run"]

        self.assertEqual(
            {"dependency-refresh-context", "dependency-refresh-resolve"},
            set(compare_job["needs"]),
        )
        for target in ROLLING_TARGETS:
            self.assertIn(target, workflow_text)
        self.assertIn("--expected-target", workflow_text)
        self.assertIn("dependency-manifest.json", workflow_text)
        self.assertIn("Rolling release is incomplete or malformed", workflow_text)
        self.assertIn("Rolling SHA256SUMS asset digest mismatch", workflow_text)
        self.assertLess(
            baseline_script.index('if python - "$release_json"'),
            baseline_script.index("gh release download dependency-latest"),
        )
        self.assertIn(
            "PY\n  then\n    mkdir -p dependency-baseline-candidate\n"
            "    gh release download dependency-latest",
            baseline_script,
        )
        self.assertIn("actual == expected", baseline_script)
        self.assertIn("--force", workflow_text)
        self.assertEqual(
            "dependency-refresh-manifest",
            compare_job["steps"][-1]["with"]["name"],
        )

    def test_dependency_refresh_reuses_offline_builds_with_frozen_wheelhouses(
        self,
    ) -> None:
        workflow = _load_ci_workflow()
        workflow_text = CI_WORKFLOW.read_text(encoding="utf-8")

        for job_id in OFFLINE_JOB_IDS:
            with self.subTest(job_id=job_id):
                job_text = repr(workflow["jobs"][job_id])
                self.assertIn("dependency-refresh-compare.outputs.source_sha", job_text)
                self.assertIn("Download frozen dependency snapshot", job_text)
                self.assertIn("resolve_offline_dependencies.py verify", job_text)
                self.assertIn("PIP_NO_INDEX", job_text)
                self.assertIn("PIP_FIND_LINKS", job_text)
        self.assertIn("runtime-wheels", workflow_text)
        self.assertIn("support-wheels", workflow_text)

    def test_rolling_prerelease_overwrites_exact_assets_and_verifies_hashes(
        self,
    ) -> None:
        workflow = _load_ci_workflow()
        workflow_text = CI_WORKFLOW.read_text(encoding="utf-8")
        release_job = workflow["jobs"]["release-dependency-refresh"]
        publish_step = next(
            step
            for step in release_job["steps"]
            if step.get("name") == "Publish rolling prerelease"
        )

        self.assertEqual(
            {"dependency-refresh-compare", *OFFLINE_JOB_IDS},
            set(release_job["needs"]),
        )
        self.assertIn("outputs.changed == 'true'", release_job["if"])
        self.assertEqual("softprops/action-gh-release@v3", publish_step["uses"])
        self.assertEqual("dependency-latest", publish_step["with"]["tag_name"])
        self.assertEqual("true", publish_step["with"]["prerelease"])
        self.assertEqual("false", publish_step["with"]["make_latest"])
        self.assertEqual("true", publish_step["with"]["overwrite_files"])
        self.assertIn("git/refs/tags/dependency-latest", workflow_text)
        self.assertIn("sha256sum", workflow_text)
        self.assertIn("Remove stale rolling release assets", workflow_text)
        self.assertIn("Published rolling tag points to", workflow_text)
        self.assertIn("Published SHA256 mismatch", workflow_text)
        self.assertEqual(11, len(ROLLING_ASSETS))
        for asset in ROLLING_ASSETS:
            self.assertIn(asset, workflow_text)

    def test_package_smoke_builds_outside_checkout_and_verifies_all_entrypoints(
        self,
    ) -> None:
        workflow = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(
            'python -m build --outdir "$RUNNER_TEMP/paper-fetch-dist"', workflow
        )
        self.assertNotIn("python -m build\n", workflow)
        self.assertNotIn("pip install dist/*.whl", workflow)
        self.assertIn('test "$("$smoke_root/bin/paper-fetch" --version)"', workflow)
        for script in (
            "paper-fetch",
            "paper-fetch-mcp",
            "paper-fetch-install-formula-tools",
            "paper-fetch-install-image-tools",
        ):
            self.assertIn(script, workflow)
        self.assertIn('paper-fetch-mcp" </dev/null', workflow)
        self.assertIn('paper-fetch" doctor --json', workflow)
        self.assertIn('provenance["consistency"]["version_drift"] == []', workflow)

    def test_ci_workflow_omits_full_unit_gate(self) -> None:
        workflow = _load_ci_workflow()
        workflow_text = CI_WORKFLOW.read_text(encoding="utf-8")

        self.assertNotIn("unit", workflow["jobs"])
        self.assertNotIn("Run unit suite", workflow_text)
        self.assertNotIn("python -m pytest tests/unit -q", workflow_text)
        self.assertNotIn("tests/unit -q --durations=30", workflow_text)
        self.assertNotIn("tests/devtools -q", workflow_text)
        self.assertNotIn("--cov=paper_fetch", workflow_text)
        self.assertNotIn("--cov-fail-under=40", workflow_text)

    def test_release_job_requires_v_tag_and_release_intent(self) -> None:
        workflow = _load_ci_workflow()
        release_job = workflow["jobs"]["release-offline-packages"]
        condition = _job_if(workflow, "release-offline-packages")

        self.assertTrue(
            {"lint", "integration", "package-smoke", *OFFLINE_JOB_IDS}.issubset(
                release_job["needs"]
            )
        )
        self.assertNotIn("unit", release_job["needs"])
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
        self.assertFalse(
            _evaluate_github_if(
                condition,
                event_name="workflow_dispatch",
                ref="refs/tags/v3.0.0",
                publish_release=True,
                force_refresh=True,
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
        self.assertIn("bash scripts/dev-preflight.sh --help", workflow)
        self.assertIn("tests/integration -q --durations=30", workflow)
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
        self.assertIn("Run MCP input schema contract", workflow)
        self.assertIn("Run dependency refresh workflow contracts", workflow)
        self.assertIn("tests/unit/test_resolve_offline_dependencies.py", workflow)
        self.assertIn("tests/unit/test_ci_release_workflow.py", workflow)
        self.assertIn("Run cross-execution surface contracts", workflow)
        for contract_path in (
            "tests/unit/test_mcp_context_budget.py",
            "tests/unit/test_mcp_provider_catalog.py",
            "tests/unit/test_skill_information_architecture.py",
            "tests/unit/test_presets_contract.py",
            "tests/unit/test_mcp_batch_fetch.py",
            "tests/unit/test_cli_run_manifest.py",
            "tests/unit/test_manifest_persistence.py",
            "tests/unit/test_install_provenance.py",
            "tests/unit/test_acceptance_adapter_contract.py",
        ):
            self.assertIn(contract_path, workflow)

    def test_live_and_full_golden_jobs_remain_manual_opt_in(self) -> None:
        workflow = _load_ci_workflow()

        full_golden = _job_if(workflow, "full-golden")
        live_mcp = _job_if(workflow, "live-mcp")
        self.assertIn("github.event_name == 'workflow_dispatch'", full_golden)
        self.assertIn("inputs.run_full_golden", full_golden)
        self.assertIn("github.event_name == 'workflow_dispatch'", live_mcp)
        self.assertIn("inputs.run_live_mcp", live_mcp)
        for job_id in ("lint", "integration", "package-smoke"):
            self.assertNotIn("tests/live", repr(workflow["jobs"][job_id]))

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
        self.assertIn("ThreadPoolExecutor(max_workers=4)", workflow)
        self.assertIn("executor.map(open_context, range(50))", workflow)
        self.assertIn("profile_dir=profile_path", workflow)
        self.assertIn('profile_path / "SingletonLock"', workflow)
        self.assertIn("singleton-recovery-*/recovery.json", workflow)
        self.assertIn(
            "data:text/html,<title>paper-fetch macOS browser smoke ", workflow
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
