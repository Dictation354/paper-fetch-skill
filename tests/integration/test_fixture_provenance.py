from __future__ import annotations

import json
import unittest

from jsonschema import Draft202012Validator

from tests.fixture_catalog import fixture_catalog
from tests.golden_criteria import GOLDEN_CRITERIA_ROOT, golden_criteria_manifest
from tests.paths import REPO_ROOT


CANONICAL_FIXTURE_PREFIXES = (
    "tests/fixtures/golden_criteria/",
    "tests/fixtures/block/",
)


class FixtureProvenanceTests(unittest.TestCase):
    def test_golden_manifest_matches_its_schema(self) -> None:
        manifest = golden_criteria_manifest()
        schema = json.loads(
            (REPO_ROOT / "quality" / "fixture-manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(manifest)), [])

    def test_manifest_sample_assets_are_cataloged_and_canonical(self) -> None:
        manifest = golden_criteria_manifest()
        catalog = fixture_catalog()
        missing: list[str] = []
        noncanonical: list[str] = []

        for sample_id, sample in manifest["samples"].items():
            for fixture_path in sample.get("assets", {}).values():
                path = REPO_ROOT / fixture_path
                if not fixture_path.startswith(CANONICAL_FIXTURE_PREFIXES):
                    noncanonical.append(f"{sample_id}: {fixture_path}")
                elif not path.is_file() or fixture_path not in catalog:
                    missing.append(f"{sample_id}: {fixture_path}")

        self.assertEqual(noncanonical, [])
        self.assertEqual(missing, [])

    def test_body_asset_files_are_registered_in_manifest_assets(self) -> None:
        manifest = golden_criteria_manifest()
        registered = {
            fixture_path
            for sample in manifest["samples"].values()
            for fixture_path in sample.get("assets", {}).values()
        }
        missing = [
            path.relative_to(REPO_ROOT).as_posix()
            for directory in sorted(GOLDEN_CRITERIA_ROOT.glob("*/body_assets"))
            for path in sorted(directory.iterdir())
            if path.is_file()
            and path.relative_to(REPO_ROOT).as_posix() not in registered
        ]

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
