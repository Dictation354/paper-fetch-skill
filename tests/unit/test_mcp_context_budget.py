from __future__ import annotations

import asyncio

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


def test_native_tools_list_omits_output_schemas() -> None:
    tools = _native_tools()
    assert len(tools) == 10
    assert all(tool.output_schema is None for tool in tools)
    listed = mcp_types.ListToolsResult(tools=tools).model_dump(
        by_alias=True, exclude_none=True
    )
    assert all("outputSchema" not in tool for tool in listed["tools"])
