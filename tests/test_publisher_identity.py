from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "publisher_identity.py"
SPEC = importlib.util.spec_from_file_location("publisher_identity", SCRIPT_PATH)
publisher_identity = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = publisher_identity
SPEC.loader.exec_module(publisher_identity)


class PublisherIdentityTests(unittest.TestCase):
    def test_normalize_doi_handles_url_and_prefix(self) -> None:
        self.assertEqual(
            publisher_identity.normalize_doi("https://doi.org/10.1016/J.RSE.2026.115369"),
            "10.1016/j.rse.2026.115369",
        )
        self.assertEqual(
            publisher_identity.normalize_doi("doi:10.1111/ABC"),
            "10.1111/abc",
        )

    def test_infer_provider_from_doi(self) -> None:
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1038/nphys1170"), "springer")
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1016/j.solener.2024.01.001"), "elsevier")
        self.assertEqual(publisher_identity.infer_provider_from_doi("10.1111/example"), "wiley")

    def test_infer_provider_from_publisher(self) -> None:
        self.assertEqual(publisher_identity.infer_provider_from_publisher("Springer Nature"), "springer")
        self.assertEqual(publisher_identity.infer_provider_from_publisher("John Wiley & Sons"), "wiley")


if __name__ == "__main__":
    unittest.main()
