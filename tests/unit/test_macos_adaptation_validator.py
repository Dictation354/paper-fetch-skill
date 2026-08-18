from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import validate_macos_adaptation as validator


class MacosAdaptationValidatorTests(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual(validator.validate_repository(), [])

    def test_duplicate_change_id_is_rejected(self) -> None:
        contract = validator.load_contract()
        duplicate = copy.deepcopy(contract["changes"][0])
        contract["changes"].append(duplicate)

        errors = validator.validate_contract(contract)

        self.assertIn(f"duplicate change id: {duplicate['id']}", errors)

    def test_missing_implementation_test_and_audit_references_are_rejected(
        self,
    ) -> None:
        contract = validator.load_contract()
        change = contract["changes"][0]
        change["implementation_paths"] = ["../outside-repository.sh"]
        change["test_nodes"] = [
            "tests/unit/test_offline_install.py::OfflineInstallTests::"
            "test_missing_macos_v4_contract"
        ]
        change["audit_cases"] = ["MAC-AUD-999"]

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn("escapes the repository", diagnostic)
        self.assertIn("pytest node does not exist", diagnostic)
        self.assertIn(
            "references undocumented audit case: MAC-AUD-999",
            diagnostic,
        )

    def test_support_matrix_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        contract["support"]["offline"]["minimum_os_version"] = "99.0"
        contract["support"]["offline"]["python_tags"] = ["cp314"]

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn("support.offline.minimum_os_version must be '15.0'", diagnostic)
        self.assertIn(
            "support.offline.python_tags must be ['cp311', 'cp312', 'cp313', 'cp314']",
            diagnostic,
        )

    def test_adapted_release_version_must_advance_past_baseline(self) -> None:
        contract = validator.load_contract()
        for project_version, should_pass in (("5.0.0", True), ("4.1.0", False)):
            with self.subTest(project_version=project_version):
                with tempfile.TemporaryDirectory() as tmpdir:
                    repo_root = Path(tmpdir)
                    (repo_root / "pyproject.toml").write_text(
                        "[project]\n"
                        f'version = "{project_version}"\n'
                        'requires-python = ">=3.11"\n',
                        encoding="utf-8",
                    )
                    errors: list[str] = []
                    validator._validate_support_values(
                        contract,
                        repo_root=repo_root,
                        errors=errors,
                    )

                version_errors = [
                    error for error in errors if error.startswith("project.version")
                ]
                if should_pass:
                    self.assertEqual(version_errors, [])
                else:
                    self.assertEqual(
                        version_errors,
                        [
                            "project.version must be greater than "
                            "source_baseline.version for an adapted release"
                        ],
                    )

    def test_build_install_and_native_verifier_safety_drift_is_rejected(
        self,
    ) -> None:
        contract = validator.load_contract()
        contract["build_safety"]["python_abi"] = "any-cpython"
        contract["build_safety"]["build_directory_policy"] = "anywhere"
        contract["build_safety"]["release_output_policy"] = "direct-write"
        contract["install_safety"]["quarantine_scan"] = "selected-files"
        contract["install_safety"]["quarantine_error_policy"] = "ignore-errors"
        contract["install_safety"]["payload_inventory_policy"] = "listed-only"
        contract["install_safety"]["host_python_isolation"] = "caller-environment"
        contract["install_safety"]["purge_symlink_policy"] = "follow"
        contract["install_safety"]["purge_path_policy"] = "raw-input"
        contract["install_safety"]["upgrade_preserves"] = []
        contract["native_verifier"]["archive_extraction"] = "system-tar"
        contract["native_verifier"]["macho_dependency_policy"] = "exists-only"
        contract["native_verifier"]["node_launch_check"] = "file-only"

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn(
            "build_safety.python_abi must be 'standard-gil-cpython'",
            diagnostic,
        )
        self.assertIn(
            "build_safety.build_directory_policy must be 'canonical-safe-root'",
            diagnostic,
        )
        self.assertIn(
            "build_safety.release_output_policy must be "
            "'same-filesystem-atomic-rename'",
            diagnostic,
        )
        self.assertIn(
            "install_safety.quarantine_scan must be 'recursive-bundle'",
            diagnostic,
        )
        self.assertIn(
            "install_safety.quarantine_error_policy must be 'fail-closed'",
            diagnostic,
        )
        self.assertIn(
            "install_safety.payload_inventory_policy must be "
            "'exact-checksummed-regular-files-no-symlinks'",
            diagnostic,
        )
        self.assertIn(
            "install_safety.host_python_isolation must be 'all-direct-invocations'",
            diagnostic,
        )
        self.assertIn(
            "install_safety.purge_symlink_policy must be 'reject'",
            diagnostic,
        )
        self.assertIn(
            "install_safety.purge_path_policy must be 'validated-normalized-path'",
            diagnostic,
        )
        self.assertIn(
            "install_safety.upgrade_preserves must be "
            "['offline.env', 'user-config-unmanaged-content']",
            diagnostic,
        )
        self.assertIn(
            "native_verifier.node_launch_check must be '--version'",
            diagnostic,
        )
        self.assertIn(
            "native_verifier.archive_extraction must be 'tarfile-data-filter'",
            diagnostic,
        )
        self.assertIn(
            "native_verifier.macho_dependency_policy must be "
            "'canonical-bundle-closure'",
            diagnostic,
        )

    def test_portable_ci_and_release_tooling_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        contract["portable_ci"]["runners"] = ["windows-latest"]
        contract["release_tooling"]["trusted_ref_format"] = "branch-or-tag"
        contract["release_tooling"]["source_tag_immutable"] = False
        contract["release_tooling"]["source_contract_required_before_overlay"] = False
        contract["release_tooling"]["legacy_source_without_contract"] = "allow"
        contract["release_tooling"][
            "overlay_copy_destinations_exclude_python_source"
        ] = False
        contract["release_tooling"]["manifest_records_tooling_revision"] = False
        contract["release_tooling"]["trusted_posix_overlay_paths"] = [
            "scripts/build-offline-package.sh"
        ]
        contract["release_tooling"]["trusted_windows_overlay_paths"] = []

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn(
            "portable_ci.runners must be ['ubuntu-latest', 'windows-latest']",
            diagnostic,
        )
        self.assertIn(
            "release_tooling.trusted_ref_format must be 'full-commit-sha'",
            diagnostic,
        )
        self.assertIn(
            "release_tooling.source_tag_immutable must be True",
            diagnostic,
        )
        self.assertIn(
            "release_tooling.source_contract_required_before_overlay must be True",
            diagnostic,
        )
        self.assertIn(
            "release_tooling.legacy_source_without_contract must be 'reject'",
            diagnostic,
        )
        self.assertIn(
            "release_tooling.overlay_copy_destinations_exclude_python_source must be True",
            diagnostic,
        )
        self.assertIn(
            "release_tooling.manifest_records_tooling_revision must be True",
            diagnostic,
        )
        self.assertIn(
            "release_tooling.trusted_posix_overlay_paths must be",
            diagnostic,
        )
        self.assertIn(
            "release_tooling.trusted_windows_overlay_paths must be",
            diagnostic,
        )

    def test_upstream_sync_constants_are_explicit(self) -> None:
        contract = validator.load_contract()

        self.assertEqual(
            contract["source_baseline"]["revision"],
            validator.EXPECTED_BASELINE_REVISION,
        )
        self.assertEqual(
            contract["contract_version"],
            validator.EXPECTED_CONTRACT_VERSION,
        )
        self.assertEqual(
            contract["release_tooling"]["trusted_posix_overlay_paths"],
            validator.EXPECTED_POSIX_TOOLING_PATHS,
        )
        self.assertEqual(
            contract["release_tooling"]["trusted_windows_overlay_paths"],
            validator.EXPECTED_WINDOWS_TOOLING_PATHS,
        )

    def test_camoufox_and_removed_flaresolverr_boundaries_are_enforced(
        self,
    ) -> None:
        contract = validator.load_contract()
        contract["components"]["camoufox"]["browser_binary"] = "bundled"
        contract["components"]["camoufox"]["python_package_specifier"] = ">=0"
        contract["components"]["camoufox"]["locked_version_source"] = "network"
        contract["components"]["camoufox"]["version_verification"] = "declaration"
        contract["components"]["camoufox"]["manifest_version_field"] = "missing"
        contract["components"]["camoufox"]["preflight_downloads_browser"] = True
        contract["components"]["camoufox"]["auto_prepare_policy"] = "always"
        contract["components"]["camoufox"]["auto_prepare_overrides"] = []
        contract["components"]["camoufox"]["managed_runtime_maintenance"] = []
        contract["components"]["camoufox"]["update_check_interval_hours"] = 0
        contract["components"]["camoufox"]["concurrency_control"] = "none"
        contract["components"]["camoufox"]["prepare_timeout_seconds"] = 0
        contract["components"]["camoufox"]["prepare_progress"] = "silent"
        contract["components"]["camoufox"]["prepare_cancellation"] = "ignored"
        contract["components"]["camoufox"]["managed_runtime_resolution"] = (
            "forced-executable-path"
        )
        contract["components"]["camoufox"]["explicit_binary_override"] = "ignored"
        contract["components"]["camoufox"]["explicit_binary_auto_prepare"] = True
        contract["components"]["camoufox"]["native_ci_runtime"] = "latest"
        contract["components"]["camoufox"]["native_test_addon_policy"] = "download"
        contract["components"]["camoufox"]["native_test_screen_policy"] = "host"
        contract["components"]["forbidden"] = []

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn(
            "components.camoufox.browser_binary must be 'not_bundled'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.python_package_specifier must be '>=0.5.4,<0.6'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.locked_version_source must be 'uv.lock'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.version_verification must be "
            "'lock-wheel-installed-manifest'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.manifest_version_field must be "
            "'components.camoufox.python_package_version'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.preflight_downloads_browser must be "
            "'cli-default-enabled-mcp-default-disabled'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.auto_prepare_policy must be "
            "'cli-default-enabled-mcp-library-default-disabled'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.auto_prepare_overrides must be "
            "['environment', 'request']",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.managed_runtime_maintenance must be "
            "['install', 'repair', 'update']",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.update_check_interval_hours must be 24",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.concurrency_control must be 'cross-process-file-lock'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.prepare_timeout_seconds must be 900",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.prepare_progress must be 'cli-stderr-mcp-logging'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.prepare_cancellation must be "
            "'cooperative-child-termination'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.managed_runtime_resolution must be "
            "'camoufox-package-managed'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.explicit_binary_override must be "
            "'configured-executable-only'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.explicit_binary_auto_prepare must be False",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.native_ci_runtime must be 'official/152.0.4-beta.28'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.native_test_addon_policy must be "
            "'exclude-default-addons'",
            diagnostic,
        )
        self.assertIn(
            "components.camoufox.native_test_screen_policy must be "
            "'fixed-synthetic-screen'",
            diagnostic,
        )
        self.assertIn(
            "components.forbidden must contain only flaresolverr",
            diagnostic,
        )

    def test_camoufox_compatible_patch_versions_are_supported(self) -> None:
        self.assertTrue(validator._camoufox_version_is_supported("0.5.4"))
        self.assertTrue(validator._camoufox_version_is_supported("0.5.99"))
        self.assertFalse(validator._camoufox_version_is_supported("0.5.3"))
        self.assertFalse(validator._camoufox_version_is_supported("0.6.0"))
        self.assertFalse(validator._camoufox_version_is_supported("latest"))

    def test_formula_toolchain_contract_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        formula_tools = contract["components"]["formula_tools"]
        formula_tools["setup_action"] = "example/setup"
        formula_tools["setup_action_version"] = "v9.9.9"
        formula_tools["setup_action_sha"] = "not-a-full-sha"
        formula_tools["ghc_version"] = "9.12.0"
        formula_tools["cabal_version"] = "3.14.0.0"
        formula_tools["ci_workflow_uses"] = 2
        formula_tools["offline_workflow_uses"] = 1
        formula_tools["node_package_manifests"] = ["package.json"]
        formula_tools["node_package_locks"] = ["package-lock.json"]
        formula_tools["katex_version"] = "0.18.1"
        formula_tools["mathml_to_latex_version"] = "1.7.0"

        diagnostic = "\n".join(validator.validate_contract(contract))

        for field in (
            "setup_action",
            "setup_action_version",
            "setup_action_sha",
            "ghc_version",
            "cabal_version",
            "ci_workflow_uses",
            "offline_workflow_uses",
            "node_package_manifests",
            "node_package_locks",
            "katex_version",
            "mathml_to_latex_version",
        ):
            self.assertIn(f"components.formula_tools.{field} must be", diagnostic)
        self.assertIn("must be a full 40-character git hash", diagnostic)

    def test_formula_toolchain_workflow_pin_and_usage_drift_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            workflows = repo_root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text(
                "      - name: Set up pinned Haskell toolchain\n"
                "        uses: example/setup@"
                f"{validator.EXPECTED_FORMULA_SETUP_SHA} "
                f"# {validator.EXPECTED_FORMULA_SETUP_VERSION}\n"
                "        with:\n"
                f'          ghc-version: "{validator.EXPECTED_FORMULA_GHC_VERSION}"\n'
                "          cabal-version: "
                f'"{validator.EXPECTED_FORMULA_CABAL_VERSION}"\n',
                encoding="utf-8",
            )
            (workflows / "offline.yml").write_text(
                "      - name: Set up pinned Haskell toolchain\n"
                "        uses: haskell-actions/setup@"
                f"{'0' * 40} # v9.9.9\n"
                "        with:\n"
                '          ghc-version: "9.12.0"\n'
                '          cabal-version: "3.14.0.0"\n',
                encoding="utf-8",
            )
            errors: list[str] = []

            validator._validate_formula_toolchain_workflows(
                repo_root=repo_root,
                errors=errors,
            )

        diagnostic = "\n".join(errors)
        self.assertIn(
            ".github/workflows/ci.yml must use haskell-actions/setup exactly "
            "1 times; got 0",
            diagnostic,
        )
        self.assertIn(
            ".github/workflows/offline.yml must use haskell-actions/setup exactly "
            "2 times; got 1",
            diagnostic,
        )
        self.assertIn("haskell-actions/setup SHA must be", diagnostic)
        self.assertIn("haskell-actions/setup version comment must be", diagnostic)
        self.assertIn("haskell-actions/setup ghc-version must be", diagnostic)
        self.assertIn("haskell-actions/setup cabal-version must be", diagnostic)

    def test_formula_node_package_drift_is_rejected(self) -> None:
        expected = validator.EXPECTED_FORMULA_NODE_DEPENDENCIES
        package = {"dependencies": expected}
        lock = {
            "packages": {
                "": {"dependencies": expected},
                **{
                    f"node_modules/{name}": {"version": version}
                    for name, version in expected.items()
                },
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            for relative_path in validator.EXPECTED_FORMULA_PACKAGE_MANIFESTS:
                path = repo_root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(package), encoding="utf-8")
            for relative_path in validator.EXPECTED_FORMULA_PACKAGE_LOCKS:
                path = repo_root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(lock), encoding="utf-8")

            bundled_package = (
                repo_root / validator.EXPECTED_FORMULA_PACKAGE_MANIFESTS[1]
            )
            bundled_package.write_text(
                json.dumps(
                    {
                        "dependencies": {
                            **expected,
                            "katex": "0.18.1",
                        }
                    }
                ),
                encoding="utf-8",
            )
            bundled_lock = repo_root / validator.EXPECTED_FORMULA_PACKAGE_LOCKS[1]
            stale_lock = json.loads(json.dumps(lock))
            stale_lock["packages"]["node_modules/katex"]["version"] = "0.18.1"
            bundled_lock.write_text(json.dumps(stale_lock), encoding="utf-8")
            errors: list[str] = []

            validator._validate_formula_node_packages(
                repo_root=repo_root,
                errors=errors,
            )

        diagnostic = "\n".join(errors)
        self.assertIn(
            "src/paper_fetch/resources/formula/package.json dependencies must be",
            diagnostic,
        )
        self.assertIn(
            "src/paper_fetch/resources/formula/package-lock.json must lock katex",
            diagnostic,
        )

    def test_release_attestation_contract_and_workflow_drift_are_rejected(
        self,
    ) -> None:
        contract = validator.load_contract()
        native_gate = contract["native_gate"]
        native_gate["release_attestation_action"] = "example/attest"
        native_gate["release_attestation_version"] = "v9.9.9"
        native_gate["release_attestation_sha"] = "not-a-full-sha"
        native_gate["release_attestation_uses"] = 2
        native_gate["release_attestation_subject_path"] = "dist/*"

        diagnostic = "\n".join(validator.validate_contract(contract))

        for field in (
            "release_attestation_action",
            "release_attestation_version",
            "release_attestation_sha",
            "release_attestation_uses",
            "release_attestation_subject_path",
        ):
            self.assertIn(f"native_gate.{field} must be", diagnostic)
        self.assertIn(
            "native_gate.release_attestation_sha must be a full 40-character git hash",
            diagnostic,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            workflow = repo_root / ".github" / "workflows" / "release.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "jobs:\n"
                "  publish:\n"
                "    steps:\n"
                "      - uses: actions/attest-build-provenance@"
                f"{'0' * 40} # v9.9.9\n"
                "        with:\n"
                "          subject-path: dist/*\n"
                "      - uses: actions/attest-build-provenance@"
                f"{validator.EXPECTED_RELEASE_ATTESTATION_SHA} "
                f"# {validator.EXPECTED_RELEASE_ATTESTATION_VERSION}\n"
                "        with:\n"
                "          subject-path: release-assets/**/*\n",
                encoding="utf-8",
            )
            errors: list[str] = []

            validator._validate_release_attestation_workflow(
                repo_root=repo_root,
                errors=errors,
            )

        diagnostic = "\n".join(errors)
        self.assertIn(
            "must use actions/attest-build-provenance exactly 1 times", diagnostic
        )
        self.assertIn("actions/attest-build-provenance SHA must be", diagnostic)
        self.assertIn(
            "actions/attest-build-provenance version comment must be",
            diagnostic,
        )
        self.assertIn(
            "must declare exactly one 'subject-path: release-assets/**/*'", diagnostic
        )

    def test_contract_keeps_portable_and_native_evidence_explicit(self) -> None:
        contract = validator.load_contract()

        self.assertEqual(
            {change["id"] for change in contract["changes"]},
            validator.EXPECTED_CHANGE_IDS,
        )
        self.assertTrue(all(change["test_nodes"] for change in contract["changes"]))
        self.assertTrue(
            any(change["native_validation_required"] for change in contract["changes"])
        )
        self.assertTrue(
            any(
                not change["native_validation_required"]
                for change in contract["changes"]
            )
        )
        self.assertFalse(
            contract["development_surfaces"]["windows"]["native_equivalent"]
        )
        self.assertFalse(contract["development_surfaces"]["wsl"]["native_equivalent"])

    def test_windows_entrypoint_rejects_unix_only_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            script = repo_root / "scripts" / "test-macos-contract.ps1"
            script.parent.mkdir(parents=True)
            script.write_text(
                "scripts/validate_macos_adaptation.py\n"
                "--print-test-nodes windows\n"
                "@testNodes\n"
                "-m pytest\n"
                "PYTHONPATH\n"
                "ValidatorOnly\n"
                "bash install-offline.sh\n",
                encoding="utf-8",
            )
            errors: list[str] = []

            validator._validate_windows_entrypoint(
                repo_root=repo_root,
                errors=errors,
            )

        self.assertIn(
            "Windows contract entrypoint invokes a non-portable dependency: bash ",
            errors,
        )

    def test_wsl_exclusions_must_be_unique_and_known(self) -> None:
        contract = validator.load_contract()
        excluded = contract["development_surfaces"]["wsl"]["excluded_test_nodes"]
        excluded.extend(
            (
                excluded[0],
                "tests/unit/test_missing.py::MissingTests::test_missing",
            )
        )

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn(
            "development_surfaces.wsl.excluded_test_nodes must not contain duplicates",
            diagnostic,
        )
        self.assertIn(
            "development_surfaces.wsl excludes an unknown pytest node",
            diagnostic,
        )

    def test_surface_node_cli_outputs_only_selected_nodes(self) -> None:
        contract = validator.load_contract()
        for surface in ("windows", "wsl"):
            with self.subTest(surface=surface):
                expected = validator.test_nodes_for_surface(contract, surface)
                result = subprocess.run(
                    [
                        sys.executable,
                        "scripts/validate_macos_adaptation.py",
                        "--print-test-nodes",
                        surface,
                    ],
                    cwd=validator.REPO_ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), expected)

    def test_wsl_entrypoint_rejects_native_or_live_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            script = repo_root / "scripts" / "test-macos-contract.sh"
            script.parent.mkdir(parents=True)
            script.write_text(
                "scripts/validate_macos_adaptation.py\n"
                ".venv-wsl/bin/python\n"
                "PYTHONPATH=\n"
                "readlink -f --\n"
                "--print-test-nodes wsl\n"
                "mapfile -t TEST_NODES\n"
                '"${TEST_NODES[@]}"\n'
                "--validator-only\n"
                "/mnt/[a-zA-Z]/*\n"
                'sys.platform != "linux"\n'
                'startswith("/mnt/")\n'
                "DEGRADED_CHECKOUT=1\n"
                "VALIDATOR_ONLY=1\n"
                "-m pytest\n"
                "tests/live\n",
                encoding="utf-8",
            )
            errors: list[str] = []

            validator._validate_wsl_entrypoint(
                repo_root=repo_root,
                errors=errors,
            )

        self.assertIn(
            "WSL/Linux contract entrypoint invokes a native/live dependency: "
            "tests/live",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
