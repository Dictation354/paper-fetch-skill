from __future__ import annotations

import asyncio

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from paper_fetch.mcp.schemas import (
    BatchFetchRequest,
    FetchPaperRequest,
    GetCachedRequest,
    ListCachedRequest,
)
from paper_fetch.mcp.server import build_server


def test_public_tool_schemas_are_valid_and_forbid_unknown_fields() -> None:
    tools = asyncio.run(build_server().list_tools())
    schemas = {tool.name: tool.input_schema for tool in tools}

    assert set(schemas) == {
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
    }
    for schema in schemas.values():
        assert schema.get("additionalProperties") is False
        Draft202012Validator.check_schema(schema)


def test_native_fetch_schema_keeps_structured_strategy_model() -> None:
    tools = asyncio.run(build_server().list_native_tools())
    fetch_schema = next(
        tool for tool in tools if tool.name == "fetch_paper"
    ).input_schema
    strategy_schema = fetch_schema["properties"]["strategy"]
    object_schema = None
    for branch in strategy_schema.get("anyOf", [strategy_schema]):
        candidate = branch
        reference = candidate.get("$ref")
        if reference:
            candidate = fetch_schema["$defs"][reference.removeprefix("#/$defs/")]
        if candidate.get("type") == "object":
            object_schema = candidate
            break

    assert object_schema is not None
    assert object_schema["additionalProperties"] is False
    assert "asset_profile" in object_schema["properties"]


@pytest.mark.parametrize(
    ("request_type", "arguments"),
    [
        (ListCachedRequest, {"unexpected": True}),
        (
            FetchPaperRequest,
            {"query": "10.1000/x", "strategy": {"asset_profile": "invalid"}},
        ),
        (GetCachedRequest, {"doi": "10.1000/x", "max_tokens": 0}),
        (BatchFetchRequest, {"queries": []}),
    ],
)
def test_representative_invalid_tool_inputs_are_rejected(
    request_type: type[BaseModel], arguments: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        request_type.model_validate(arguments)
