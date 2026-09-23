from __future__ import annotations

import json
import hashlib
import unittest
from dataclasses import replace
from unittest import mock

from jsonschema import Draft202012Validator

from tests.fixture_catalog import fixture_catalog
from tests.golden_criteria import GOLDEN_CRITERIA_ROOT, golden_criteria_manifest
from tests.paths import REPO_ROOT
from tests.block_fixtures import BLOCK_FIXTURE_ROOT


CANONICAL_FIXTURE_PREFIXES = (
    "tests/fixtures/golden_criteria/",
    "tests/fixtures/block/",
)


class FixtureProvenanceTests(unittest.TestCase):
    def test_disproven_source_bytes_cannot_be_promoted_to_real(self) -> None:
        catalog = fixture_catalog()
        rows = golden_criteria_manifest()["rejected_sources"]
        for row in rows:
            if row.get("retired"):
                # Retired publisher bytes are registered only as synthetic
                # infrastructure inputs, never as active paper content.
                record = catalog[row["legacy_path"]]
                self.assertEqual(record.usage_kind, "infrastructure")
                self.assertEqual(record.fixture_family, "scenario")
                self.assertNotIn(
                    row["sample_id"], golden_criteria_manifest()["samples"]
                )
                self.assertFalse((GOLDEN_CRITERIA_ROOT / row["sample_id"]).exists())
            else:
                record = catalog[row["legacy_path"]]
            with self.subTest(path=record.fixture_path):
                self.assertEqual(record.origin_kind, row["classification"])
                self.assertEqual(
                    hashlib.sha256(record.absolute_path.read_bytes()).hexdigest(),
                    row["sha256"],
                )
                with mock.patch(
                    "tests.fixture_catalog._iter_manifest_records",
                    return_value=[replace(record, origin_kind="real_replay")],
                ):
                    with self.assertRaisesRegex(ValueError, "Disproven real source"):
                        fixture_catalog.__wrapped__()

    def test_real_declaration_and_checksum_do_not_establish_network_origin(
        self,
    ) -> None:
        from tests.support.fixture_provenance import source_evidence

        record = next(
            r
            for r in fixture_catalog().values()
            if r.origin_kind == "real_replay" and r.absolute_path.suffix == ".html"
        )
        result = source_evidence(record, {}, {})
        self.assertEqual(result["status"], "unverified")
        unrelated_identity = {("10.0000/unrelated", result["sha256"]): [{}]}
        self.assertEqual(
            source_evidence(record, unrelated_identity, {})["status"], "unverified"
        )

    def test_replacements_have_same_identity_captured_bytes(self) -> None:
        from tests.support.fixture_provenance import (
            capture_index,
            rejected_source_hashes,
            source_evidence,
        )

        catalog = fixture_catalog()
        index = capture_index()
        rejected = rejected_source_hashes()
        for row in golden_criteria_manifest()["rejected_sources"]:
            if not row["replacement_path"]:
                continue  # Explicitly recorded acquisition gaps, never real claims.
            with self.subTest(path=row["replacement_path"]):
                record = catalog[row["replacement_path"]]
                self.assertEqual(
                    record.doi.lower(),
                    row.get("replacement_doi", catalog[row["legacy_path"]].doi).lower(),
                )
                self.assertEqual(
                    source_evidence(record, index, rejected)["status"],
                    "verified_capture",
                )

    def test_acquisition_bytes_match_recorded_hashes_and_catalog(self) -> None:
        catalog = fixture_catalog()
        for path in sorted(
            list(GOLDEN_CRITERIA_ROOT.glob("*/acquisition/provenance.json"))
            + list(BLOCK_FIXTURE_ROOT.glob("*/acquisition/provenance.json"))
        ):
            records = json.loads(path.read_text(encoding="utf-8"))["records"]
            for record in records:
                body_path = path.parent.parent / record["body_file"]
                with self.subTest(path=body_path.relative_to(REPO_ROOT).as_posix()):
                    self.assertIn(body_path.relative_to(REPO_ROOT).as_posix(), catalog)
                    body = body_path.read_bytes()
                    self.assertEqual(len(body), record["size"])
                    self.assertEqual(hashlib.sha256(body).hexdigest(), record["sha256"])

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
            for asset_key, fixture_path in sample.get("assets", {}).items():
                path = REPO_ROOT / fixture_path
                self.assertEqual(
                    catalog[fixture_path].origin_kind,
                    sample.get("asset_origins", {}).get(
                        asset_key, sample["origin_kind"]
                    ),
                )
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


def test_deduplicated_capture_aliases_resolve_to_the_recorded_entity():
    from tests.golden_criteria import golden_criteria_asset

    aliases = 0
    for provenance in GOLDEN_CRITERIA_ROOT.glob("*/acquisition/provenance.json"):
        for record in json.loads(provenance.read_text())["records"]:
            if "original_body_file" not in record:
                continue
            physical = provenance.parent.parent / record["body_file"]
            logical = golden_criteria_asset(record["doi"], record["original_body_file"])
            assert logical == physical
            assert hashlib.sha256(logical.read_bytes()).hexdigest() == record["sha256"]
            aliases += 1
    assert aliases > 0
