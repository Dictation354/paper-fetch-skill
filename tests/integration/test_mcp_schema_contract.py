from __future__ import annotations

import os
import sys
import unittest
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from paper_fetch.provider_catalog import (
    browser_preflight_provider_names,
    provider_status_order,
)
from tests.paths import REPO_ROOT, SRC_DIR


def _object_branch(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") == "object":
        return schema
    return next(
        branch for branch in schema.get("anyOf", []) if branch.get("type") == "object"
    )


def _array_branch(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") == "array":
        return schema
    return next(
        branch for branch in schema.get("anyOf", []) if branch.get("type") == "array"
    )


def _enum_values(schema: dict[str, Any]) -> list[str]:
    if "enum" in schema:
        return schema["enum"]
    return next(
        branch["enum"] for branch in schema.get("anyOf", []) if "enum" in branch
    )


def _integer_branch(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") == "integer":
        return schema
    return next(
        branch for branch in schema.get("anyOf", []) if branch.get("type") == "integer"
    )


class McpStdioSchemaContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_tools_list_host_safe_input_schema_snapshot(self) -> None:
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "paper_fetch.mcp.server"],
            cwd=str(REPO_ROOT),
            env={**os.environ, "PYTHONPATH": str(SRC_DIR)},
        )

        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed = await session.list_tools()

        schemas = {tool.name: tool.input_schema for tool in listed.tools}
        fetch = schemas["fetch_paper"]
        strategy = _object_branch(fetch["properties"]["strategy"])
        batch_resolve = schemas["batch_resolve"]
        batch_check = schemas["batch_check"]
        batch_fetch = schemas["batch_fetch"]
        get_cached = schemas["get_cached"]
        get_cached_strategy = _object_branch(get_cached["properties"]["strategy"])
        provider_status = schemas["provider_status"]
        browser_preflight = schemas["browser_preflight"]
        snapshot = {
            "tools": sorted(schemas),
            "all_extra_forbid": all(
                schema.get("additionalProperties") is False
                for schema in schemas.values()
            ),
            "strategy": {
                "type": strategy.get("type"),
                "additionalProperties": strategy.get("additionalProperties"),
                "asset_profile": _enum_values(strategy["properties"]["asset_profile"]),
            },
            "include_refs": _enum_values(fetch["properties"]["include_refs"]),
            "artifact_mode": _enum_values(fetch["properties"]["artifact_mode"]),
            "cache_mode": _enum_values(
                schemas["list_cached"]["properties"]["cache_mode"]
            ),
            "batch_mode": _enum_values(batch_check["properties"]["mode"]),
            "queries": {
                "minItems": batch_resolve["properties"]["queries"]["minItems"],
                "maxItems": batch_resolve["properties"]["queries"]["maxItems"],
            },
            "concurrency": {
                "minimum": batch_check["properties"]["concurrency"]["minimum"],
                "maximum": batch_check["properties"]["concurrency"]["maximum"],
            },
            "batch_fetch": {
                "queries": {
                    "minItems": batch_fetch["properties"]["queries"]["minItems"],
                    "maxItems": batch_fetch["properties"]["queries"]["maxItems"],
                },
                "concurrency": {
                    "minimum": batch_fetch["properties"]["concurrency"]["minimum"],
                    "maximum": batch_fetch["properties"]["concurrency"]["maximum"],
                },
                "detail": _enum_values(batch_fetch["properties"]["detail"]),
                "content_max_chars": {
                    "minimum": batch_fetch["properties"]["content_max_chars"][
                        "minimum"
                    ],
                    "maximum": batch_fetch["properties"]["content_max_chars"][
                        "maximum"
                    ],
                },
                "modes": _enum_values(
                    _array_branch(batch_fetch["properties"]["modes"])["items"]
                ),
            },
            "get_cached": {
                "detail": _enum_values(get_cached["properties"]["detail"]),
                "preferred_only_type": get_cached["properties"]["preferred_only"][
                    "type"
                ],
                "modes": _enum_values(
                    _array_branch(get_cached["properties"]["modes"])["items"]
                ),
                "include_refs": _enum_values(get_cached["properties"]["include_refs"]),
                "asset_profile": _enum_values(
                    get_cached_strategy["properties"]["asset_profile"]
                ),
            },
            "provider_status": {
                "provider": _enum_values(provider_status["properties"]["provider"]),
                "group": _enum_values(provider_status["properties"]["group"]),
                "detail": _enum_values(provider_status["properties"]["detail"]),
            },
            "browser_preflight": {
                "provider": _enum_values(browser_preflight["properties"]["provider"]),
                "detail": _enum_values(browser_preflight["properties"]["detail"]),
                "timeout_ms": {
                    "minimum": _integer_branch(
                        browser_preflight["properties"]["timeout_ms"]
                    )["minimum"],
                    "maximum": _integer_branch(
                        browser_preflight["properties"]["timeout_ms"]
                    )["maximum"],
                },
            },
        }
        self.assertEqual(
            snapshot,
            {
                "tools": [
                    "batch_check",
                    "batch_fetch",
                    "batch_resolve",
                    "browser_preflight",
                    "fetch_paper",
                    "get_cached",
                    "has_fulltext",
                    "list_cached",
                    "provider_status",
                    "resolve_paper",
                ],
                "all_extra_forbid": True,
                "strategy": {
                    "type": "object",
                    "additionalProperties": False,
                    "asset_profile": ["none", "body", "all"],
                },
                "include_refs": ["none", "top10", "all"],
                "artifact_mode": ["markdown-assets", "all", "none"],
                "cache_mode": ["index", "refresh", "rescan"],
                "batch_mode": ["article", "metadata"],
                "queries": {"minItems": 1, "maxItems": 50},
                "concurrency": {"minimum": 1, "maximum": 8},
                "batch_fetch": {
                    "queries": {"minItems": 1, "maxItems": 50},
                    "concurrency": {"minimum": 1, "maximum": 8},
                    "detail": ["compact", "bounded"],
                    "content_max_chars": {"minimum": 1, "maximum": 100000},
                    "modes": ["article", "markdown", "metadata"],
                },
                "get_cached": {
                    "detail": ["full", "compact"],
                    "preferred_only_type": "boolean",
                    "modes": ["article", "markdown", "metadata"],
                    "include_refs": ["none", "top10", "all"],
                    "asset_profile": ["none", "body", "all"],
                },
                "provider_status": {
                    "provider": list(provider_status_order()),
                    "group": [
                        "all",
                        "official",
                        "browser",
                        "direct",
                        "metadata",
                    ],
                    "detail": ["full", "compact"],
                },
                "browser_preflight": {
                    "provider": list(browser_preflight_provider_names()),
                    "detail": ["full", "compact"],
                    "timeout_ms": {"minimum": 1, "maximum": 600000},
                },
            },
        )

        def assert_reference_free(value: Any) -> None:
            if isinstance(value, dict):
                self.assertNotIn("$ref", value)
                for child in value.values():
                    assert_reference_free(child)
            elif isinstance(value, list):
                for child in value:
                    assert_reference_free(child)

        for schema in schemas.values():
            assert_reference_free(schema)


if __name__ == "__main__":
    unittest.main()
