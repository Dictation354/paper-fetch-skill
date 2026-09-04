from __future__ import annotations

import asyncio
import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

from paper_fetch.mcp.schemas import (
    BatchFetchRequest,
    BrowserPreflightRequest,
    FetchPaperRequest,
    FetchPaperToolRequest,
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
        assert '"$ref"' not in json.dumps(schema)
        Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize(
    ("tool_name", "request_type", "field_names", "defaults"),
    [
        (
            "fetch_paper",
            FetchPaperToolRequest,
            [
                "query",
                "modes",
                "strategy",
                "include_refs",
                "max_tokens",
                "prefer_cache",
                "no_download",
                "artifact_mode",
                "save_markdown",
                "markdown_output_dir",
                "markdown_filename",
                "download_dir",
            ],
            {
                "modes": None,
                "strategy": None,
                "include_refs": None,
                "max_tokens": "full_text",
                "prefer_cache": False,
                "no_download": False,
                "artifact_mode": "markdown-assets",
                "save_markdown": False,
                "markdown_output_dir": None,
                "markdown_filename": None,
                "download_dir": None,
            },
        ),
        (
            "get_cached",
            GetCachedRequest,
            [
                "doi",
                "download_dir",
                "detail",
                "preferred_only",
                "modes",
                "strategy",
                "include_refs",
                "max_tokens",
            ],
            {
                "download_dir": None,
                "detail": "full",
                "preferred_only": False,
                "modes": None,
                "strategy": None,
                "include_refs": None,
                "max_tokens": "full_text",
            },
        ),
        (
            "batch_fetch",
            BatchFetchRequest,
            [
                "queries",
                "concurrency",
                "modes",
                "strategy",
                "include_refs",
                "max_tokens",
                "prefer_cache",
                "no_download",
                "artifact_mode",
                "save_markdown",
                "markdown_output_dir",
                "markdown_filename",
                "download_dir",
                "detail",
                "content_max_chars",
                "continue_on_error",
                "batch_results",
                "overwrite",
            ],
            {
                "concurrency": 1,
                "modes": None,
                "strategy": None,
                "include_refs": None,
                "max_tokens": "full_text",
                "prefer_cache": False,
                "no_download": False,
                "artifact_mode": "markdown-assets",
                "save_markdown": False,
                "markdown_output_dir": None,
                "markdown_filename": None,
                "download_dir": None,
                "detail": "compact",
                "content_max_chars": 20_000,
                "continue_on_error": True,
                "batch_results": None,
                "overwrite": False,
            },
        ),
    ],
)
def test_native_fetch_signatures_stay_aligned_with_request_models(
    tool_name: str,
    request_type: type[BaseModel],
    field_names: list[str],
    defaults: dict[str, object],
) -> None:
    tools = asyncio.run(build_server().list_native_tools())
    schema = next(tool for tool in tools if tool.name == tool_name).input_schema

    assert list(schema["properties"]) == field_names
    assert set(request_type.model_fields) == set(field_names)
    assert {
        name: property_schema["default"]
        for name, property_schema in schema["properties"].items()
        if "default" in property_schema
    } == defaults


def test_shared_fetch_options_keep_null_normalization_and_conversion() -> None:
    options = {
        "modes": None,
        "strategy": None,
        "include_refs": " TOP10 ",
        "max_tokens": "2048",
    }
    expected = FetchPaperRequest.model_validate({"query": "10.1000/example", **options})

    batch_request = BatchFetchRequest.model_validate(
        {"queries": ["10.1000/example"], **options}
    )
    cached_request = GetCachedRequest.model_validate(
        {"doi": "10.1000/example", **options}
    )

    assert batch_request.to_fetch_request("10.1000/example") == expected
    assert cached_request.to_fetch_request() == expected


def test_single_and_batch_fetch_normalize_optional_paths_consistently() -> None:
    single = FetchPaperRequest.model_validate(
        {
            "query": "10.1000/example",
            "markdown_output_dir": "  ./papers  ",
            "markdown_filename": "  paper.md  ",
        }
    )
    batch = BatchFetchRequest.model_validate(
        {
            "queries": ["10.1000/example"],
            "markdown_output_dir": "  ./papers  ",
            "markdown_filename": "  paper.md  ",
            "download_dir": "  ./cache  ",
            "batch_results": "  ./results.jsonl  ",
        }
    )

    assert batch.markdown_output_dir == single.markdown_output_dir == "./papers"
    assert batch.markdown_filename == single.markdown_filename == "paper.md"
    assert batch.download_dir == "./cache"
    assert batch.batch_results == "./results.jsonl"


@pytest.mark.parametrize(
    ("request_type", "required_arguments", "field_name"),
    [
        (
            FetchPaperToolRequest,
            {"query": "10.1000/example"},
            "markdown_output_dir",
        ),
        (
            FetchPaperToolRequest,
            {"query": "10.1000/example"},
            "markdown_filename",
        ),
        (FetchPaperToolRequest, {"query": "10.1000/example"}, "download_dir"),
        (
            BatchFetchRequest,
            {"queries": ["10.1000/example"]},
            "markdown_output_dir",
        ),
        (
            BatchFetchRequest,
            {"queries": ["10.1000/example"]},
            "markdown_filename",
        ),
        (BatchFetchRequest, {"queries": ["10.1000/example"]}, "download_dir"),
        (BatchFetchRequest, {"queries": ["10.1000/example"]}, "batch_results"),
        (ListCachedRequest, {}, "download_dir"),
        (GetCachedRequest, {"doi": "10.1000/example"}, "download_dir"),
        (BrowserPreflightRequest, {"provider": "wiley"}, "storage_state_path"),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        (" \t ", None),
        ("  value with  internal space  ", "value with  internal space"),
    ],
)
def test_optional_string_fields_share_strip_only_normalization(
    request_type: type[BaseModel],
    required_arguments: dict[str, object],
    field_name: str,
    value: str | None,
    expected: str | None,
) -> None:
    request = request_type.model_validate({**required_arguments, field_name: value})

    assert getattr(request, field_name) == expected


def test_batch_fetch_treats_blank_shared_filename_as_unspecified() -> None:
    request = BatchFetchRequest.model_validate(
        {
            "queries": ["10.1000/one", "10.1000/two"],
            "markdown_filename": "   ",
        }
    )

    assert request.markdown_filename is None
    assert all(
        request.to_fetch_request(query).markdown_filename is None
        for query in request.queries
    )


def test_native_batch_fetch_schema_keeps_bounded_limits() -> None:
    tools = asyncio.run(build_server().list_native_tools())
    schema = next(tool for tool in tools if tool.name == "batch_fetch").input_schema

    assert schema["properties"]["queries"]["minItems"] == 1
    assert schema["properties"]["queries"]["maxItems"] == 50
    assert schema["properties"]["concurrency"]["minimum"] == 1
    assert schema["properties"]["concurrency"]["maximum"] == 8


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
