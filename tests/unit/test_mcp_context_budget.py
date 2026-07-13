from __future__ import annotations

import asyncio
import json

from mcp import types as mcp_types

from paper_fetch.mcp._instructions import (
    fetch_tool_description,
    server_instructions,
)
from paper_fetch.mcp.provider_catalog import PROVIDER_CATALOG_RESOURCE_URI
from paper_fetch.mcp.server import build_server

SERVER_INSTRUCTIONS_MAX_CHARS = 1_500
FETCH_DESCRIPTION_MAX_CHARS = 1_200
ALL_TOOL_DESCRIPTIONS_MAX_CHARS = 5_000
HOST_NARRATIVE_MAX_CHARS = 24_000

# PF-018 snapshot for the ten-tool native contract after adding structured batch_fetch.
# The allowance is only for small schema metadata drift, not new unbudgeted tools.
NATIVE_TOOLS_LIST_BASELINE_BYTES = 74_411
NATIVE_TOOLS_LIST_GROWTH_ALLOWANCE_BYTES = 1_024
NATIVE_SCHEMA_BASELINE_BYTES = 70_913
NATIVE_SCHEMA_GROWTH_ALLOWANCE_BYTES = 512


def _native_tools() -> list[mcp_types.Tool]:
    return asyncio.run(build_server().list_native_tools())


def test_mcp_instruction_and_description_budgets() -> None:
    server = build_server()
    instructions = server_instructions()
    descriptions = [
        tool.description or "" for tool in server._tool_manager._tools.values()
    ]

    assert len(instructions) <= SERVER_INSTRUCTIONS_MAX_CHARS
    assert len(fetch_tool_description()) <= FETCH_DESCRIPTION_MAX_CHARS
    assert sum(map(len, descriptions)) <= ALL_TOOL_DESCRIPTIONS_MAX_CHARS
    assert (
        len(descriptions) * len(instructions) + sum(map(len, descriptions))
        <= HOST_NARRATIVE_MAX_CHARS
    )
    assert PROVIDER_CATALOG_RESOURCE_URI in instructions
    assert PROVIDER_CATALOG_RESOURCE_URI in fetch_tool_description()
    assert "may write" in instructions
    assert "may open" in instructions
    assert "no_download=true" in fetch_tool_description()


def test_native_tools_list_and_schema_size_snapshots() -> None:
    tools = _native_tools()
    assert len(tools) == 10

    tools_result = mcp_types.ListToolsResult(tools=tools)
    tools_list_bytes = len(
        tools_result.model_dump_json(by_alias=True, exclude_none=True).encode()
    )
    schema_payload = [
        {
            "name": tool.name,
            "inputSchema": tool.inputSchema,
            "outputSchema": tool.outputSchema,
        }
        for tool in tools
    ]
    schema_bytes = len(
        json.dumps(
            schema_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )

    assert (
        NATIVE_TOOLS_LIST_BASELINE_BYTES - NATIVE_TOOLS_LIST_GROWTH_ALLOWANCE_BYTES
        <= tools_list_bytes
        <= NATIVE_TOOLS_LIST_BASELINE_BYTES + NATIVE_TOOLS_LIST_GROWTH_ALLOWANCE_BYTES
    )
    assert (
        NATIVE_SCHEMA_BASELINE_BYTES - NATIVE_SCHEMA_GROWTH_ALLOWANCE_BYTES
        <= schema_bytes
        <= NATIVE_SCHEMA_BASELINE_BYTES + NATIVE_SCHEMA_GROWTH_ALLOWANCE_BYTES
    )
