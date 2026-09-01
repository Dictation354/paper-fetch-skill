from __future__ import annotations

import asyncio
import unittest

from mcp import Client
from mcp.types.version import LATEST_MODERN_VERSION

from paper_fetch.mcp.server import build_server
from paper_fetch.version import __version__


class McpServerV2ApiTests(unittest.TestCase):
    def test_v2_client_negotiates_modern_protocol(self) -> None:
        async def exercise_client() -> None:
            async with Client(build_server()) as client:
                self.assertEqual(client.protocol_version, LATEST_MODERN_VERSION)
                self.assertEqual(client.server_info.version, __version__)

                listed = await client.list_tools()
                self.assertIn("provider_status", {tool.name for tool in listed.tools})
                result = await client.call_tool(
                    "provider_status", {"detail": "compact"}
                )
                self.assertFalse(result.is_error)

        asyncio.run(exercise_client())
