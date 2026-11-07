from __future__ import annotations

import copy
import unittest

from scripts import validate_macos_adaptation as validator


class MacosAdaptationValidatorTests(unittest.TestCase):
    def test_update_entry_preserves_installer_boundaries(self) -> None:
        contract = validator.load_contract()
        for key, value in contract["update"].items():
            contract["update"][key] = False if value is True else "other"
        diagnostics = "\n".join(validator.validate_contract(contract))
        for key in contract["update"]:
            self.assertIn(f"update.{key} must be", diagnostics)

    def test_support_matrix_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        contract["support"]["offline"]["python_versions"] = ["3.14"]
        contract["support"]["offline"]["architectures"] = ["x86_64"]

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn("python_versions must match", diagnostic)
        self.assertIn("architectures must match", diagnostic)

    def test_safety_invariants_fail_closed(self) -> None:
        contract = copy.deepcopy(validator.load_contract())
        contract["safety"]["reject_symlinks"] = False

        self.assertIn(
            "safety.reject_symlinks must be true",
            validator.validate_contract(contract),
        )

    def test_browser_boundary_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        contract["browser"]["runtime_bundle_built_in"] = True
        contract["browser"]["default_backend"] = "camoufox"
        contract["browser"]["pnas_backend"] = "camoufox"
        contract["browser"]["elsevier_browser_routes"] = "camoufox"
        contract["browser"]["system_chrome_required"] = True
        contract["browser"]["installer_prepares_byparr"] = False
        contract["browser"]["native_bundle_gate"] = False
        contract["browser"]["managed_runtime_preparation"] = False
        contract["browser"]["fetch_start_preparation"] = True
        contract["browser"]["batch_prepares_once"] = False
        contract["browser"]["installer_preparation_single_pass"] = False
        contract["browser"]["default_channel"] = "official/stable"
        contract["browser"]["prerelease_includes_stable"] = False
        contract["browser"]["update_check_interval_seconds"] = 0
        contract["browser"]["python_package_spec"] = "camoufox>=0.5.9"
        contract["browser"]["cooperative_cancel_owner_thread_cleanup"] = False
        contract["browser"]["html_snapshot_owner_thread"] = False
        contract["browser"]["supplementary_index_without_body"] = False
        for key in (
            "fingerprint_model_github_api_fallback",
            "fingerprint_model_before_playwright",
            "publisher_native_persistent_profiles",
            "profile_exclusive_lock_owner_thread",
            "auth_native_profile_replay",
            "json_export_optional",
        ):
            contract["browser"][key] = False

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn("runtime_bundle_built_in must be false", diagnostic)
        self.assertIn("default_backend must be byparr", diagnostic)
        self.assertIn("pnas_backend must be byparr", diagnostic)
        self.assertIn("elsevier_browser_routes must be supported", diagnostic)
        self.assertIn("system_chrome_required must be false", diagnostic)
        self.assertIn("installer_prepares_byparr must be true", diagnostic)
        self.assertIn("native_bundle_gate must be true", diagnostic)
        self.assertIn("managed_runtime_preparation must be true", diagnostic)
        self.assertIn("fetch_start_preparation must be false", diagnostic)
        self.assertIn("batch_prepares_once must be true", diagnostic)
        self.assertIn("installer_preparation_single_pass must be true", diagnostic)
        self.assertIn("default_channel must be official/prerelease", diagnostic)
        self.assertIn("prerelease_includes_stable must be true", diagnostic)
        self.assertIn("update_check_interval_seconds must be 86400", diagnostic)
        self.assertIn("python_package_spec must be camoufox==0.5.9", diagnostic)
        self.assertIn(
            "cooperative_cancel_owner_thread_cleanup must be true", diagnostic
        )
        self.assertIn("html_snapshot_owner_thread must be true", diagnostic)
        self.assertIn("supplementary_index_without_body must be true", diagnostic)
        for key in (
            "fingerprint_model_github_api_fallback",
            "fingerprint_model_before_playwright",
            "publisher_native_persistent_profiles",
            "profile_exclusive_lock_owner_thread",
            "auth_native_profile_replay",
            "json_export_optional",
        ):
            self.assertIn(f"{key} must be true", diagnostic)

    def test_codex_discovery_and_migration_contract_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        contract["skills"]["codex"]["user_directory"] = (
            "~/.codex/skills/paper-fetch-skill"
        )
        contract["skills"]["codex"]["project_directory"] = (
            ".codex/skills/paper-fetch-skill"
        )
        contract["skills"]["codex"]["verify_before_legacy_cleanup"] = False
        contract["skills"]["codex"]["check_is_read_only"] = False
        diagnostics = "\n".join(validator.validate_contract(contract))
        for key in contract["skills"]["codex"]:
            self.assertIn(f"skills.codex.{key} must be", diagnostics)

    def test_release_policy_keeps_build_evidence_private(self) -> None:
        contract = validator.load_contract()
        contract["release"]["build_evidence_is_not_public"] = False

        self.assertIn(
            "release.build_evidence_is_not_public must be true",
            validator.validate_contract(contract),
        )

    def test_optional_download_cannot_change_core_offline_boundary(self) -> None:
        contract = validator.load_contract()
        contract["browser"]["core_install_downloads_runtime"] = False
        contract["browser"]["optional_install_download_requires_consent"] = True
        contract["browser"]["optional_install_failure_preserves_core"] = False
        diagnostic = "\n".join(validator.validate_contract(contract))
        self.assertIn("core_install_downloads_runtime must be true", diagnostic)
        self.assertIn(
            "optional_install_download_requires_consent must be false", diagnostic
        )
        self.assertIn(
            "optional_install_failure_preserves_core must be true", diagnostic
        )

    def test_release_policy_requires_one_source_revision(self) -> None:
        contract = validator.load_contract()
        contract["release"]["single_source_revision"] = False

        self.assertIn(
            "release.single_source_revision must be true",
            validator.validate_contract(contract),
        )


if __name__ == "__main__":
    unittest.main()
