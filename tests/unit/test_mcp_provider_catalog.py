from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from unittest import mock

from paper_fetch import provider_catalog as runtime_catalog
from paper_fetch.config import DEFAULT_USER_AGENT
from paper_fetch.mcp.provider_catalog import (
    PROVIDER_CATALOG_RESOURCE_URI,
    PROVIDER_CATALOG_SCHEMA_VERSION,
    provider_catalog_resource_payload,
)
from paper_fetch.mcp.server import build_server


def test_provider_catalog_payload_exactly_reflects_runtime_catalog() -> None:
    payload = provider_catalog_resource_payload()
    specs = runtime_catalog.ordered_provider_specs()

    assert payload["schema_version"] == PROVIDER_CATALOG_SCHEMA_VERSION
    assert payload["tool_version"] == DEFAULT_USER_AGENT.removeprefix(
        "paper-fetch-skill/"
    )
    assert payload["resource_uri"] == PROVIDER_CATALOG_RESOURCE_URI
    assert payload["provider_count"] == len(specs)
    assert payload["source_count"] == len(runtime_catalog.SOURCE_PROVIDER_MAP)
    assert payload["source_provider_map"] == dict(
        sorted(runtime_catalog.SOURCE_PROVIDER_MAP.items())
    )
    assert [item["provider"] for item in payload["providers"]] == [
        spec.name for spec in specs
    ]

    sources_by_provider = runtime_catalog.sources_by_provider()
    for item, spec in zip(payload["providers"], specs, strict=True):
        assert item == {
            "provider": spec.name,
            "display_name": spec.display_name,
            "official": spec.official,
            "sources": sorted(sources_by_provider.get(spec.name, ())),
            "asset_default": spec.asset_default,
            "capabilities": {
                "html": spec.html_capable,
                "metadata_probe": spec.probe_capability or None,
                "provider_managed_abstract_only": (spec.provider_managed_abstract_only),
                "runtime_kind": (
                    "browser" if spec.requires_browser_runtime else "direct"
                ),
                "requires_browser_runtime": spec.requires_browser_runtime,
                "requires_playwright": spec.requires_playwright,
                "supports_static_status": True,
                "supports_browser_preflight": spec.requires_browser_runtime,
            },
        }


def test_provider_catalog_payload_automatically_includes_discovered_changes() -> None:
    existing_specs = dict(runtime_catalog.PROVIDER_CATALOG)
    synthetic = replace(
        next(iter(existing_specs.values())),
        name="synthetic",
        display_name="Synthetic Provider",
        official=True,
        status_order=max(spec.status_order for spec in existing_specs.values()) + 1,
        asset_default="all",
        probe_capability="metadata_api",
        requires_playwright=True,
        requires_browser_runtime=True,
    )
    updated_specs = {**existing_specs, synthetic.name: synthetic}
    updated_sources = {
        **dict(runtime_catalog.SOURCE_PROVIDER_MAP),
        "synthetic_html": synthetic.name,
    }

    with (
        mock.patch.object(runtime_catalog, "PROVIDER_CATALOG", updated_specs),
        mock.patch.object(runtime_catalog, "SOURCE_PROVIDER_MAP", updated_sources),
    ):
        payload = provider_catalog_resource_payload()

    synthetic_payload = payload["providers"][-1]
    assert synthetic_payload["provider"] == synthetic.name
    assert synthetic_payload["sources"] == ["synthetic_html"]
    assert synthetic_payload["asset_default"] == "all"
    assert synthetic_payload["capabilities"]["supports_browser_preflight"] is True
    assert payload["source_provider_map"]["synthetic_html"] == synthetic.name
    assert payload["provider_count"] == len(existing_specs) + 1
    assert payload["source_count"] == len(updated_sources)


def test_server_registers_readable_provider_catalog_resource() -> None:
    async def read_resource() -> tuple[str, str | None]:
        server = build_server()
        resource = await server._resource_manager.get_resource(
            PROVIDER_CATALOG_RESOURCE_URI
        )
        assert resource is not None
        return await resource.read(), resource.mime_type

    raw_payload, mime_type = asyncio.run(read_resource())
    assert mime_type == "application/json"
    assert isinstance(raw_payload, str)
    assert json.loads(raw_payload) == provider_catalog_resource_payload()
