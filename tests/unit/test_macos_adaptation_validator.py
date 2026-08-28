from __future__ import annotations

import copy
import unittest

from scripts import validate_macos_adaptation as validator


class MacosAdaptationValidatorTests(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual(validator.validate_repository(), [])

    def test_support_matrix_drift_is_rejected(self) -> None:
        contract = validator.load_contract()
        contract["support"]["offline"]["python_versions"] = ["3.14"]
        contract["support"]["offline"]["architectures"] = ["x86_64"]

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn("python_versions must match", diagnostic)
        self.assertIn("architectures must match", diagnostic)

    def test_portable_evidence_cannot_claim_native_equivalence(self) -> None:
        contract = validator.load_contract()
        contract["evidence"]["portable"]["native_equivalent"] = True

        self.assertIn(
            "portable evidence must not claim native equivalence",
            validator.validate_contract(contract),
        )

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
        contract["browser"]["native_bundle_gate"] = False

        diagnostic = "\n".join(validator.validate_contract(contract))

        self.assertIn("runtime_bundle_built_in must be false", diagnostic)
        self.assertIn("native_bundle_gate must be true", diagnostic)

    def test_release_policy_keeps_build_evidence_private(self) -> None:
        contract = validator.load_contract()
        contract["release"]["build_evidence_is_not_public"] = False

        self.assertIn(
            "release.build_evidence_is_not_public must be true",
            validator.validate_contract(contract),
        )


if __name__ == "__main__":
    unittest.main()
