from __future__ import annotations

import copy
import unittest

from scripts import validate_macos_adaptation as validator


class MacosAdaptationValidatorTests(unittest.TestCase):
    def test_current_contract_is_valid(self) -> None:
        self.assertEqual(validator.validate_repository(), [])

    def test_node_runtime_contract_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        for key, value in contract["node_runtime"].items():
            contract["node_runtime"][key] = False if value is True else "other"
        diagnostics = "\n".join(validator.validate_contract(contract))
        for key in contract["node_runtime"]:
            self.assertIn(f"node_runtime.{key} must be", diagnostics)

    def test_interpreter_selection_contract_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        keys = ("python_default", "python_override_option", "python_override_env")
        for key in keys:
            contract["support"]["offline"][key] = "other"
        diagnostics = "\n".join(validator.validate_contract(contract))
        for key in keys:
            self.assertIn(f"support.offline.{key} must be", diagnostics)

    def test_native_evidence_workflow_path_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        contract["evidence"]["native"]["release_matrix_workflow"] = (
            ".github/workflows/missing.yml"
        )
        diagnostics = "\n".join(validator.validate_contract(contract))
        self.assertIn(
            "evidence.native.release_matrix_workflow must point to .github/workflows/offline.yml",
            diagnostics,
        )

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
        contract["browser"]["native_engine"] = "invisible"
        contract["browser"]["default_backend"] = "other"
        contract["browser"]["system_chrome_required"] = True
        contract["browser"]["runtime_bundle_built_in"] = True
        contract["browser"]["python_requirements"] = ["scrapling>=0.5.1"]

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn(
            "browser.native_engine must match browser_runtime_policy on darwin",
            diagnostic,
        )
        self.assertIn("browser.default_backend must be scrapling", diagnostic)
        self.assertIn("browser.python_requirements must match the pinned", diagnostic)
        self.assertIn("browser.system_chrome_required must be false", diagnostic)
        self.assertIn("browser.runtime_bundle_built_in must be false", diagnostic)

    def test_codex_discovery_contract_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        contract["skills"]["codex"]["user_directory"] = (
            "~/.codex/skills/paper-fetch-skill"
        )
        contract["skills"]["codex"]["project_directory"] = (
            ".codex/skills/paper-fetch-skill"
        )
        contract["skills"]["codex"]["current_skill_path_only"] = False
        contract["skills"]["codex"]["check_is_read_only"] = False
        diagnostics = "\n".join(validator.validate_contract(contract))
        for key in contract["skills"]["codex"]:
            self.assertIn(f"skills.codex.{key} must be", diagnostics)

    def test_release_policy_keeps_build_evidence_private_and_single_revision(
        self,
    ) -> None:
        contract = validator.load_contract()
        contract["release"]["build_evidence_is_not_public"] = False
        contract["release"]["single_source_revision"] = False

        diagnostics = validator.validate_contract(contract)
        self.assertIn(
            "release.build_evidence_is_not_public must be true",
            diagnostics,
        )
        self.assertIn(
            "release.single_source_revision must be true",
            diagnostics,
        )


if __name__ == "__main__":
    unittest.main()
