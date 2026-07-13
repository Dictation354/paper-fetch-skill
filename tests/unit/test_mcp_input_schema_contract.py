from __future__ import annotations

import asyncio
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import TypeAdapter, ValidationError

from paper_fetch.auth import browser_auth_provider_names
from paper_fetch.mcp.schemas import (
    BatchFetchRequest,
    BrowserPreflightRequest,
    CacheDetailInput,
    FetchStrategyInput,
    GetCachedRequest,
    host_safe_tool_input_schema,
)
from paper_fetch.mcp.server import build_server
from paper_fetch.provider_catalog import provider_status_order


def _property(schema: dict[str, Any], name: str) -> dict[str, Any]:
    return schema["properties"][name]


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


def _integer_branch(schema: dict[str, Any]) -> dict[str, Any]:
    if schema.get("type") == "integer":
        return schema
    return next(
        branch for branch in schema.get("anyOf", []) if branch.get("type") == "integer"
    )


def _enum_values(schema: dict[str, Any]) -> list[str]:
    if "enum" in schema:
        return schema["enum"]
    return next(
        branch["enum"] for branch in schema.get("anyOf", []) if "enum" in branch
    )


def _constraint_snapshot(schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fetch = schemas["fetch_paper"]
    strategy = _object_branch(_property(fetch, "strategy"))
    batch_resolve = schemas["batch_resolve"]
    batch_check = schemas["batch_check"]
    batch_fetch = schemas["batch_fetch"]
    get_cached = schemas["get_cached"]
    get_cached_strategy = _object_branch(_property(get_cached, "strategy"))
    provider_status = schemas["provider_status"]
    browser_preflight = schemas["browser_preflight"]
    return {
        "all_extra_forbid": all(
            schema.get("additionalProperties") is False for schema in schemas.values()
        ),
        "modes": _enum_values(_array_branch(_property(fetch, "modes"))["items"]),
        "include_refs": _enum_values(_property(fetch, "include_refs")),
        "asset_profile": _enum_values(_property(strategy, "asset_profile")),
        "artifact_mode": _enum_values(_property(fetch, "artifact_mode")),
        "cache_mode": _enum_values(_property(schemas["list_cached"], "cache_mode")),
        "batch_mode": _enum_values(_property(batch_check, "mode")),
        "queries": {
            "minItems": _property(batch_resolve, "queries")["minItems"],
            "maxItems": _property(batch_resolve, "queries")["maxItems"],
        },
        "concurrency": {
            "minimum": _property(batch_check, "concurrency")["minimum"],
            "maximum": _property(batch_check, "concurrency")["maximum"],
        },
        "batch_fetch": {
            "queries": {
                "minItems": _property(batch_fetch, "queries")["minItems"],
                "maxItems": _property(batch_fetch, "queries")["maxItems"],
            },
            "concurrency": {
                "minimum": _property(batch_fetch, "concurrency")["minimum"],
                "maximum": _property(batch_fetch, "concurrency")["maximum"],
            },
            "detail": _enum_values(_property(batch_fetch, "detail")),
            "content_max_chars": {
                "minimum": _property(batch_fetch, "content_max_chars")["minimum"],
                "maximum": _property(batch_fetch, "content_max_chars")["maximum"],
            },
            "modes": _enum_values(
                _array_branch(_property(batch_fetch, "modes"))["items"]
            ),
        },
        "get_cached": {
            "detail": _enum_values(_property(get_cached, "detail")),
            "preferred_only_type": _property(get_cached, "preferred_only")["type"],
            "modes": _enum_values(
                _array_branch(_property(get_cached, "modes"))["items"]
            ),
            "include_refs": _enum_values(_property(get_cached, "include_refs")),
            "asset_profile": _enum_values(
                _property(get_cached_strategy, "asset_profile")
            ),
        },
        "provider_status": {
            "provider": _enum_values(_property(provider_status, "provider")),
            "group": _enum_values(_property(provider_status, "group")),
            "detail": _enum_values(_property(provider_status, "detail")),
        },
        "browser_preflight": {
            "provider": _enum_values(_property(browser_preflight, "provider")),
            "detail": _enum_values(_property(browser_preflight, "detail")),
            "timeout_ms": {
                "minimum": _integer_branch(_property(browser_preflight, "timeout_ms"))[
                    "minimum"
                ],
                "maximum": _integer_branch(_property(browser_preflight, "timeout_ms"))[
                    "maximum"
                ],
            },
        },
        "strategy": {
            "type": strategy["type"],
            "additionalProperties": strategy["additionalProperties"],
            "fields": list(strategy["properties"]),
        },
    }


EXPECTED_CONSTRAINT_SNAPSHOT = {
    "all_extra_forbid": True,
    "modes": ["article", "markdown", "metadata"],
    "include_refs": ["none", "top10", "all"],
    "asset_profile": ["none", "body", "all"],
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
        "group": ["all", "official", "browser", "direct", "metadata"],
        "detail": ["full", "compact"],
    },
    "browser_preflight": {
        "provider": list(browser_auth_provider_names()),
        "detail": ["full", "compact"],
        "timeout_ms": {"minimum": 1, "maximum": 600000},
    },
    "strategy": {
        "type": "object",
        "additionalProperties": False,
        "fields": [
            "allow_metadata_only_fallback",
            "preferred_providers",
            "asset_profile",
            "inline_image_budget",
        ],
    },
}


def test_native_fastmcp_input_schema_snapshot_is_draft_2020_12_and_typed() -> None:
    server = build_server()
    tools = asyncio.run(server.list_native_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}

    assert _constraint_snapshot(schemas) == EXPECTED_CONSTRAINT_SNAPSHOT
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)


def test_host_safe_normalized_input_schema_snapshot_has_no_references() -> None:
    server = build_server()
    tools = asyncio.run(server.list_tools())
    schemas = {tool.name: tool.inputSchema for tool in tools}

    assert _constraint_snapshot(schemas) == EXPECTED_CONSTRAINT_SNAPSHOT
    assert schemas == {name: host_safe_tool_input_schema(name) for name in schemas}

    def assert_reference_free(value: Any) -> None:
        if isinstance(value, dict):
            assert "$ref" not in value
            for child in value.values():
                assert_reference_free(child)
        elif isinstance(value, list):
            for child in value:
                assert_reference_free(child)

    for schema in schemas.values():
        assert_reference_free(schema)
        Draft202012Validator.check_schema(schema)


def test_shared_cache_detail_literal_schema_and_normalization_snapshot() -> None:
    adapter = TypeAdapter(CacheDetailInput)

    assert adapter.json_schema() == {
        "enum": ["full", "compact"],
        "type": "string",
    }
    assert adapter.validate_python(" COMPACT ") == "compact"


def test_native_runtime_legacy_nested_strategy_stays_typed() -> None:
    tool = build_server()._tool_manager._tools["fetch_paper"]
    parsed = tool.fn_metadata.arg_model.model_validate(
        {
            "query": "10.1000/example",
            "modes": ["ARTICLE", "markdown"],
            "strategy": {
                "asset_profile": "BODY",
                "inline_image_budget": {"max_images": 2},
            },
            "include_refs": "TOP10",
            "artifact_mode": "ALL",
        }
    )

    assert isinstance(parsed.strategy, FetchStrategyInput)
    assert parsed.strategy.asset_profile == "body"
    assert parsed.strategy.inline_image_budget is not None
    assert parsed.strategy.inline_image_budget.max_images == 2
    assert parsed.modes == ["article", "markdown"]
    assert parsed.include_refs == "top10"
    assert parsed.artifact_mode == "all"

    server = build_server()
    cache_args = server._tool_manager._tools[
        "list_cached"
    ].fn_metadata.arg_model.model_validate({"cache_mode": " RESCAN "})
    batch_args = server._tool_manager._tools[
        "batch_check"
    ].fn_metadata.arg_model.model_validate(
        {"queries": [" 10.1000/example "], "mode": " ARTICLE ", "concurrency": 2}
    )
    assert cache_args.cache_mode == "rescan"
    assert batch_args.mode == "article"
    assert batch_args.queries == ["10.1000/example"]

    batch_fetch_args = BatchFetchRequest.model_validate(
        {
            "queries": [" 10.1000/example "],
            "modes": ["MARKDOWN"],
            "strategy": {"asset_profile": "NONE"},
            "artifact_mode": "NONE",
            "detail": " BOUNDED ",
            "content_max_chars": 512,
        }
    )
    assert batch_fetch_args.queries == ["10.1000/example"]
    assert batch_fetch_args.modes == ["markdown"]
    assert batch_fetch_args.strategy.asset_profile == "none"
    assert batch_fetch_args.artifact_mode == "none"
    assert batch_fetch_args.detail == "bounded"
    assert batch_fetch_args.content_max_chars == 512

    browser_args = BrowserPreflightRequest.model_validate(
        {
            "provider": " WILEY ",
            "test_url": " https://onlinelibrary.wiley.com/doi/full/10.1111/x ",
            "storage_state_path": " /tmp/state path /wiley.json ",
            "detail": " COMPACT ",
        }
    )
    assert browser_args.provider == "wiley"
    assert browser_args.test_url == (
        "https://onlinelibrary.wiley.com/doi/full/10.1111/x"
    )
    assert browser_args.storage_state_path == "/tmp/state path /wiley.json"
    assert browser_args.detail == "compact"

    cached_args = GetCachedRequest.model_validate(
        {
            "doi": " 10.1000/example ",
            "detail": " COMPACT ",
            "preferred_only": True,
            "modes": ["ARTICLE"],
            "strategy": {"asset_profile": "BODY"},
            "include_refs": "TOP10",
            "max_tokens": 512,
        }
    )
    assert cached_args.doi == "10.1000/example"
    assert cached_args.detail == "compact"
    assert cached_args.preferred_only is True
    assert cached_args.modes == ["article"]
    assert cached_args.strategy.asset_profile == "body"
    assert cached_args.include_refs == "top10"
    assert cached_args.max_tokens == 512


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("fetch_paper", {"query": "10.1000/x", "modes": ["invalid"]}),
        (
            "fetch_paper",
            {"query": "10.1000/x", "strategy": {"asset_profile": "invalid"}},
        ),
        (
            "fetch_paper",
            {"query": "10.1000/x", "strategy": {"unexpected": True}},
        ),
        ("fetch_paper", {"query": "10.1000/x", "include_refs": "invalid"}),
        ("fetch_paper", {"query": "10.1000/x", "artifact_mode": "invalid"}),
        ("fetch_paper", {"query": "10.1000/x", "unexpected": True}),
        ("list_cached", {"cache_mode": "invalid"}),
        ("get_cached", {"doi": "10.1000/x", "detail": "invalid"}),
        ("get_cached", {"doi": "10.1000/x", "modes": ["invalid"]}),
        (
            "get_cached",
            {"doi": "10.1000/x", "strategy": {"asset_profile": "invalid"}},
        ),
        ("get_cached", {"doi": "10.1000/x", "include_refs": "invalid"}),
        ("get_cached", {"doi": "10.1000/x", "max_tokens": 0}),
        ("get_cached", {"doi": "10.1000/x", "unexpected": True}),
        ("batch_resolve", {"queries": []}),
        ("batch_resolve", {"queries": [str(index) for index in range(51)]}),
        ("batch_resolve", {"queries": ["x"], "concurrency": 0}),
        ("batch_resolve", {"queries": ["x"], "concurrency": 9}),
        ("batch_check", {"queries": ["x"], "mode": "invalid"}),
        ("batch_fetch", {"queries": []}),
        ("batch_fetch", {"queries": [str(index) for index in range(51)]}),
        ("batch_fetch", {"queries": ["x"], "concurrency": 0}),
        ("batch_fetch", {"queries": ["x"], "concurrency": 9}),
        ("batch_fetch", {"queries": ["x"], "detail": "invalid"}),
        ("batch_fetch", {"queries": ["x"], "content_max_chars": 0}),
        ("batch_fetch", {"queries": ["x"], "content_max_chars": 100001}),
        ("batch_fetch", {"queries": ["x"], "modes": ["invalid"]}),
        (
            "batch_fetch",
            {"queries": ["x"], "strategy": {"asset_profile": "invalid"}},
        ),
        ("batch_fetch", {"queries": ["x"], "artifact_mode": "invalid"}),
        ("batch_fetch", {"queries": ["x"], "unexpected": True}),
        ("provider_status", {"provider": "invalid"}),
        ("provider_status", {"group": "invalid"}),
        ("provider_status", {"detail": "invalid"}),
        ("browser_preflight", {"provider": "invalid"}),
        ("browser_preflight", {"detail": "invalid"}),
        ("browser_preflight", {"provider": "wiley", "timeout_ms": 0}),
        ("browser_preflight", {"provider": "wiley", "timeout_ms": 600001}),
    ],
)
def test_native_invalid_input_fails_before_registered_tool_invocation(
    tool_name: str, arguments: dict[str, Any]
) -> None:
    server = build_server()
    tool = server._tool_manager._tools[tool_name]
    invoked = False

    async def should_not_run(**_: Any) -> None:
        nonlocal invoked
        invoked = True

    tool.fn = should_not_run
    tool.is_async = True

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(server._tool_manager.call_tool(tool_name, arguments))

    assert isinstance(exc_info.value.__cause__, ValidationError)
    assert invoked is False
