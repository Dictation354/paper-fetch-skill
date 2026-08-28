from __future__ import annotations

import ast
import json
import re
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

from tests.fixture_catalog import fixture_catalog
from tests.golden_criteria import GOLDEN_CRITERIA_ROOT, golden_criteria_manifest
from tests.paths import REPO_ROOT


DOC_PATH = REPO_ROOT / "docs" / "extraction-rules.md"
CANONICAL_FIXTURE_PREFIXES = (
    "tests/fixtures/golden_criteria/",
    "tests/fixtures/block/",
)
FORBIDDEN_SOURCE_SNIPPETS = (
    "paywall-samples",
    "live-downloads",
    "md_for_lc_body",
    "geography_golden",
)
DOC_FIXTURE_PATH_RE = re.compile(r"\.\./(tests/fixtures/.*?\.(?:html|xml|md|json))")


def _module_test_names(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


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
                    continue
                if not path.is_file():
                    missing.append(f"{sample_id}: {fixture_path}")
                    continue
                if fixture_path not in catalog:
                    missing.append(f"{sample_id}: {fixture_path} (uncataloged)")

        self.assertEqual(
            noncanonical,
            [],
            "Non-canonical manifest assets:\n" + "\n".join(noncanonical),
        )
        self.assertEqual(
            missing,
            [],
            "Missing or uncataloged manifest assets:\n" + "\n".join(missing),
        )

    def test_body_asset_files_are_registered_in_manifest_assets(self) -> None:
        manifest = golden_criteria_manifest()
        registered = {
            fixture_path
            for sample in manifest["samples"].values()
            for fixture_path in sample.get("assets", {}).values()
        }
        missing: list[str] = []

        for body_assets_dir in sorted(GOLDEN_CRITERIA_ROOT.glob("*/body_assets")):
            for asset_path in sorted(
                path for path in body_assets_dir.iterdir() if path.is_file()
            ):
                fixture_path = asset_path.relative_to(REPO_ROOT).as_posix()
                if fixture_path not in registered:
                    missing.append(fixture_path)

        self.assertEqual(
            missing, [], "Unregistered body_assets files:\n" + "\n".join(missing)
        )

    def test_manifest_test_mappings_are_complete_and_resolve(self) -> None:
        manifest = golden_criteria_manifest()
        docs = DOC_PATH.read_text(encoding="utf-8")
        anchors = set(re.findall(r'<a id="([^"]+)">', docs))
        missing: list[str] = []

        for entry in manifest["tests"]:
            if not all(key in entry for key in ("test", "anchors", "samples")):
                missing.append(f"incomplete mapping: {entry!r}")
                continue
            module_name, test_name = entry["test"].split("::", 1)
            module_path = REPO_ROOT / module_name
            if not module_path.is_file():
                missing.append(f"{entry['test']} (missing module)")
                continue
            if test_name not in _module_test_names(module_path):
                missing.append(f"{entry['test']} (missing test)")
            if not entry["anchors"]:
                missing.append(f"{entry['test']} (empty anchors)")
            for anchor in entry["anchors"]:
                if anchor not in anchors:
                    missing.append(f"{entry['test']} (missing anchor #{anchor})")
            for sample_id in entry["samples"]:
                if sample_id not in manifest["samples"]:
                    missing.append(f"{entry['test']} (missing sample {sample_id})")

        self.assertEqual(missing, [], "Manifest/doc mismatches:\n" + "\n".join(missing))

    def test_registered_rule_test_modules_only_reference_canonical_rule_assets(
        self,
    ) -> None:
        manifest = golden_criteria_manifest()
        offending: list[str] = []

        for module_name in sorted(
            {entry["test"].split("::", 1)[0] for entry in manifest["tests"]}
        ):
            source = (REPO_ROOT / module_name).read_text(encoding="utf-8")
            for snippet in FORBIDDEN_SOURCE_SNIPPETS:
                if snippet in source:
                    offending.append(
                        f"{module_name}: contains forbidden source reference `{snippet}`"
                    )
            for literal in re.findall(r"tests/fixtures/[^\"')\\s]+", source):
                if not literal.startswith(CANONICAL_FIXTURE_PREFIXES):
                    offending.append(
                        f"{module_name}: contains non-canonical fixture literal `{literal}`"
                    )

        self.assertEqual(
            offending,
            [],
            "Registered rule modules reference non-canonical assets:\n"
            + "\n".join(offending),
        )

    def test_rule_docs_only_link_canonical_fixture_assets(self) -> None:
        docs = DOC_PATH.read_text(encoding="utf-8")
        bad_links: list[str] = []

        for line in docs.splitlines():
            for relative_path in DOC_FIXTURE_PATH_RE.findall(line):
                path = REPO_ROOT / relative_path
                if not relative_path.startswith(CANONICAL_FIXTURE_PREFIXES):
                    bad_links.append(relative_path)
                    continue
                if not path.is_file():
                    bad_links.append(f"{relative_path} (missing)")

        self.assertEqual(
            bad_links,
            [],
            "Rule docs contain non-canonical or missing fixture links:\n"
            + "\n".join(bad_links),
        )

    def test_manifest_file_itself_lives_under_golden_criteria(self) -> None:
        self.assertTrue((GOLDEN_CRITERIA_ROOT / "manifest.json").is_file())

    def test_legacy_fixture_roots_and_flat_files_are_removed(self) -> None:
        self.assertFalse((REPO_ROOT / "paywall-samples").exists())
        self.assertFalse(
            (REPO_ROOT / "tests" / "fixtures" / "geography_golden").exists()
        )
        remaining_files = [
            path.name
            for path in (REPO_ROOT / "tests" / "fixtures").iterdir()
            if path.is_file() and path.name != "README.md"
        ]
        self.assertEqual(
            remaining_files,
            [],
            "Legacy flat fixture files remain:\n" + "\n".join(sorted(remaining_files)),
        )


if __name__ == "__main__":
    unittest.main()
