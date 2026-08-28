from __future__ import annotations

from pathlib import Path

import pytest

from ._manifest_sync import (
    DRAFT_COMPATIBLE_SYNC_BACK_STATUSES,
    KNOWN_PROVIDERS_PATH,
    REPO_ROOT,
    SOURCE_PROVIDER_MAP,
    STRICT_SYNC_BACK_STATUSES,
    ManifestCase,
    assert_synced,
    drift_message,
    is_strict_sync_back_status,
    iter_manifest_cases,
    load_known_provider_entries,
    manifest_asset_default,
    normalized_publisher,
    normalized_sequence,
    serialize_bundle_sync_back,
    source_is_registered_or_placeholder,
    sync_back_value_is_unset,
)


def _case_id(case: ManifestCase) -> str:
    return case.provider


@pytest.mark.parametrize("case", iter_manifest_cases(), ids=_case_id)
def test_manifest_routing_probe_asset_and_source_match_provider_bundle(
    case: ManifestCase,
) -> None:
    manifest = case.manifest
    routing = manifest["routing"]
    probe = manifest["probe"]
    catalog = case.bundle.catalog

    assert_synced(case, "name", manifest["name"], catalog.name)
    provider_module = Path(
        catalog.client_factory_path.partition(":")[0].replace(".", "/")
    )
    assert_synced(case, "provider module stem", manifest["name"], provider_module.stem)
    assert_synced(
        case,
        "routing.doi_prefixes",
        normalized_sequence(routing["doi_prefixes"]),
        normalized_sequence(catalog.doi_prefixes),
    )
    assert_synced(
        case,
        "routing.domains",
        tuple(routing["domains"]),
        catalog.domains,
    )
    assert_synced(
        case,
        "routing.domain_suffixes",
        tuple(routing["domain_suffixes"]),
        catalog.domain_suffixes,
    )

    crossref_publisher = routing["crossref_publisher"]
    if crossref_publisher is not None:
        publisher_aliases = {
            normalized_publisher(value) for value in catalog.publisher_aliases
        }
        assert normalized_publisher(crossref_publisher) in publisher_aliases, (
            drift_message(
                provider=case.provider,
                manifest_path=case.manifest_path,
                field_path="routing.crossref_publisher",
                manifest_value=crossref_publisher,
                code_value=sorted(publisher_aliases),
            )
        )

    assert_synced(
        case, "asset_profile", manifest_asset_default(manifest), catalog.asset_default
    )
    if manifest["abstract_only_strategy"] == "provider_managed":
        assert_synced(
            case,
            "abstract_only_strategy",
            True,
            catalog.provider_managed_abstract_only,
        )
    assert_synced(
        case,
        "probe.env_requirements",
        tuple(probe["env_requirements"]),
        catalog.env_requirements,
    )
    display_source = str(manifest["display_source"])
    assert source_is_registered_or_placeholder(display_source, case.bundle), (
        drift_message(
            provider=case.provider,
            manifest_path=case.manifest_path,
            field_path="display_source",
            manifest_value=display_source,
            code_value={
                "bundle.sources": case.bundle.sources,
                "SOURCE_PROVIDER_MAP[display_source]": SOURCE_PROVIDER_MAP.get(
                    display_source
                ),
            },
        )
    )
    route_sources = manifest.get("route_sources") or {}
    assert set(route_sources) <= set(manifest["main_path"]), drift_message(
        provider=case.provider,
        manifest_path=case.manifest_path,
        field_path="route_sources",
        manifest_value=route_sources,
        code_value={"main_path": manifest["main_path"]},
    )
    if route_sources:
        assert display_source in set(route_sources.values()), drift_message(
            provider=case.provider,
            manifest_path=case.manifest_path,
            field_path="route_sources",
            manifest_value=route_sources,
            code_value={"display_source": display_source},
        )
    for step, source in route_sources.items():
        assert source_is_registered_or_placeholder(str(source), case.bundle), (
            drift_message(
                provider=case.provider,
                manifest_path=case.manifest_path,
                field_path=f"route_sources.{step}",
                manifest_value=source,
                code_value={
                    "bundle.sources": case.bundle.sources,
                    "SOURCE_PROVIDER_MAP[source]": SOURCE_PROVIDER_MAP.get(str(source)),
                },
            )
        )


def test_known_providers_manifest_paths_and_statuses_do_not_conflict() -> None:
    allowed_statuses = (
        STRICT_SYNC_BACK_STATUSES
        | DRAFT_COMPATIBLE_SYNC_BACK_STATUSES
        | {
            "infrastructure",
        }
    )

    for entry in load_known_provider_entries():
        provider = str(entry["name"])
        status = str(entry["status"])
        manifest_value = entry.get("manifest_path")
        assert status in allowed_statuses, (
            f"{KNOWN_PROVIDERS_PATH.relative_to(REPO_ROOT)}: provider={provider}: "
            f"unsupported status {status!r}"
        )
        if status in STRICT_SYNC_BACK_STATUSES | {"draft", "implemented"}:
            assert manifest_value is not None, (
                f"{KNOWN_PROVIDERS_PATH.relative_to(REPO_ROOT)}: provider={provider}: "
                f"status {status!r} requires manifest_path"
            )
        if manifest_value is None:
            assert status == "infrastructure", (
                f"{KNOWN_PROVIDERS_PATH.relative_to(REPO_ROOT)}: provider={provider}: "
                "only infrastructure status may omit manifest_path"
            )
        if manifest_value is not None:
            manifest_path = REPO_ROOT / str(manifest_value)
            assert manifest_path.is_file(), (
                f"{KNOWN_PROVIDERS_PATH.relative_to(REPO_ROOT)}: provider={provider}: "
                f"manifest path does not exist: {manifest_value}"
            )
            assert status != "infrastructure", (
                f"{KNOWN_PROVIDERS_PATH.relative_to(REPO_ROOT)}: provider={provider}: "
                "infrastructure status cannot point at a provider manifest"
            )


@pytest.mark.parametrize("case", iter_manifest_cases(), ids=_case_id)
def test_manifest_sync_back_fields_match_provider_bundle_when_strict(
    case: ManifestCase,
) -> None:
    manifest_hints = case.manifest["extraction_hints"]
    code_hints = serialize_bundle_sync_back(case.bundle)

    for field_name, code_value in code_hints.items():
        manifest_value = manifest_hints[field_name]
        if not is_strict_sync_back_status(case.status) and sync_back_value_is_unset(
            manifest_value
        ):
            continue
        assert_synced(
            case,
            f"extraction_hints.{field_name}",
            manifest_value,
            code_value,
        )

    if not is_strict_sync_back_status(case.status):
        return

    success_criteria = case.manifest["success_criteria"]
    for step in case.manifest["main_path"]:
        assert step in success_criteria and success_criteria[step] is not None, (
            drift_message(
                provider=case.provider,
                manifest_path=case.manifest_path,
                field_path=f"success_criteria.{step}",
                manifest_value=success_criteria.get(step),
                code_value="non-null sync-back value required for production provider",
            )
        )
