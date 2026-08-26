"""Machine-readable MCP view of the runtime provider catalog."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from ..config import DEFAULT_USER_AGENT
from .. import provider_catalog as runtime_catalog

PROVIDER_CATALOG_RESOURCE_URI = "resource://paper-fetch/provider-catalog"
PROVIDER_CATALOG_SCHEMA_VERSION = 1


def _route_payload(route: Any) -> dict[str, Any]:
    """Return a route mapping whose containers already match its JSON form."""

    return json.loads(json.dumps(asdict(route)))


def _compiled_route_payload(provider: str, route: Any) -> dict[str, Any]:
    payload = _route_payload(route)
    payload["execution_policy"] = json.loads(
        json.dumps(
            asdict(runtime_catalog.compile_route_execution_policy(provider, route.name))
        )
    )
    return payload


def runtime_tool_version() -> str:
    prefix = "paper-fetch-skill/"
    return (
        DEFAULT_USER_AGENT.removeprefix(prefix)
        if DEFAULT_USER_AGENT.startswith(prefix)
        else DEFAULT_USER_AGENT
    )


def provider_catalog_resource_payload() -> dict[str, Any]:
    """Build the resource directly from the discovered provider/source catalog."""

    grouped_sources = runtime_catalog.sources_by_provider()
    providers = [
        {
            "provider": spec.name,
            "display_name": spec.display_name,
            "official": spec.official,
            "sources": sorted(grouped_sources.get(spec.name, ())),
            "asset_default": spec.asset_default,
            "routes": [
                _compiled_route_payload(spec.name, route) for route in spec.routes
            ],
            "capabilities": {
                "html": spec.html_capable,
                "metadata_probe": spec.probe_capability or None,
                "provider_managed_abstract_only": (spec.provider_managed_abstract_only),
                "runtime_kind": (
                    "browser"
                    if runtime_catalog.provider_requires_browser(spec.name)
                    else (
                        "hybrid"
                        if runtime_catalog.provider_has_browser_route(spec.name)
                        else "direct"
                    )
                ),
                "requires_browser_runtime": spec.requires_browser_runtime,
                "browser_required": runtime_catalog.provider_requires_browser(
                    spec.name
                ),
                "browser_optional": any(
                    route.browser_optional for route in spec.routes
                ),
                "requires_playwright": spec.requires_playwright,
                "supports_static_status": True,
                "supports_browser_preflight": (
                    runtime_catalog.provider_supports_browser_preflight(spec.name)
                ),
                "auth_supported": runtime_catalog.provider_supports_auth(spec.name),
                "pdf_conversion": runtime_catalog.provider_requires_pdf_conversion(
                    spec.name
                ),
            },
        }
        for spec in runtime_catalog.ordered_provider_specs()
    ]
    source_provider_map = dict(sorted(runtime_catalog.SOURCE_PROVIDER_MAP.items()))
    return {
        "schema_version": PROVIDER_CATALOG_SCHEMA_VERSION,
        "tool_version": runtime_tool_version(),
        "resource_uri": PROVIDER_CATALOG_RESOURCE_URI,
        "provider_count": len(providers),
        "source_count": len(source_provider_map),
        "providers": providers,
        "source_provider_map": source_provider_map,
    }


__all__ = [
    "PROVIDER_CATALOG_RESOURCE_URI",
    "PROVIDER_CATALOG_SCHEMA_VERSION",
    "provider_catalog_resource_payload",
    "runtime_tool_version",
]
