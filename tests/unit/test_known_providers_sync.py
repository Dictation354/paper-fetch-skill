from __future__ import annotations

import paper_fetch.providers  # noqa: F401
from paper_fetch.provider_catalog import PROVIDER_CATALOG
from paper_fetch.providers._registry import iter_provider_bundles

from ._manifest_sync import (
    MANIFESTS_DIR,
    REPO_ROOT,
    load_known_provider_entries,
    load_yaml,
)


def known_provider_entries():
    return load_known_provider_entries()


def test_known_providers_match_runtime_provider_names() -> None:
    known_names = [entry["name"] for entry in known_provider_entries()]
    bundle_names = [bundle.catalog.name for bundle in iter_provider_bundles()]
    catalog_names = list(PROVIDER_CATALOG)

    assert known_names == bundle_names
    assert known_names == catalog_names


def test_known_providers_manifest_paths_are_synced() -> None:
    entries = known_provider_entries()
    by_name = {entry["name"]: entry for entry in entries}
    manifest_paths = sorted(MANIFESTS_DIR.glob("*.yml"))
    manifest_names = {path.stem for path in manifest_paths}
    indexed_manifest_names = {
        entry["name"] for entry in entries if entry.get("manifest_path") is not None
    }

    assert indexed_manifest_names == manifest_names
    for entry in entries:
        provider = entry["name"]
        status = entry["status"]
        manifest_path = entry.get("manifest_path")
        if status == "implemented":
            assert manifest_path is not None, (
                f"{provider} implemented provider needs manifest_path"
            )
        if manifest_path is None:
            assert status == "infrastructure", (
                f"{provider} is {status!r}; only infrastructure providers may omit manifest_path"
            )

    for manifest_path in manifest_paths:
        manifest = load_yaml(manifest_path)
        entry = by_name[manifest["name"]]
        indexed_path = entry["manifest_path"]
        assert indexed_path == str(manifest_path.relative_to(REPO_ROOT))
        assert (REPO_ROOT / indexed_path).is_file()
        assert manifest["name"] == manifest_path.stem
        assert manifest["display_source"] == entry["display_source"]
        assert manifest["display_source"].startswith(manifest["name"])


def test_catalog_provider_names_all_appear_in_known_providers() -> None:
    known_names = {entry["name"] for entry in known_provider_entries()}

    assert set(PROVIDER_CATALOG) <= known_names
