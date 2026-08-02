from __future__ import annotations

import copy
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
        for project_version, should_pass in (("4.2.0", True), ("4.1.0", False)):
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
        contract["components"]["camoufox"]["managed_runtime_resolution"] = (
            "forced-executable-path"
        )
        contract["components"]["camoufox"]["explicit_binary_override"] = "ignored"
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
            "components.camoufox.preflight_downloads_browser must be False",
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
