# ruff: noqa: F403,F405
from __future__ import annotations

from mcp import Client
from mcp.server.lowlevel.server import NotificationOptions
from mcp.types.version import LATEST_MODERN_VERSION

from paper_fetch.version import __version__

from ._mcp_support import *


class McpServerV2ApiTests(unittest.TestCase):
    def test_build_server_uses_mcpserver_resource_registry(self) -> None:
        server = build_server()

        self.assertIsInstance(server._resource_manager._resources, dict)

    def test_build_server_advertises_resource_list_changed_capability(self) -> None:
        server = build_server()

        options = server._lowlevel_server.create_initialization_options(
            NotificationOptions(resources_changed=True)
        )

        self.assertIsNotNone(options.capabilities.resources)
        self.assertTrue(options.capabilities.resources.list_changed)

    def test_build_server_uses_mcpserver_stdio_run_surface(self) -> None:
        server = build_server()

        self.assertTrue(callable(server.run_stdio_async))
        self.assertTrue(callable(server._lowlevel_server.run))
        self.assertTrue(callable(server._lowlevel_server.create_initialization_options))

    def test_v2_client_negotiates_modern_protocol(self) -> None:
        async def exercise_client() -> None:
            async with Client(build_server()) as client:
                self.assertEqual(client.protocol_version, LATEST_MODERN_VERSION)
                self.assertEqual(client.server_info.version, __version__)
                self.assertTrue(client.server_capabilities.resources.list_changed)

                listed = await client.list_tools()
                self.assertEqual(len(listed.tools), 10)
                result = await client.call_tool(
                    "provider_status", {"detail": "compact"}
                )
                self.assertFalse(result.is_error)

        asyncio.run(exercise_client())

    def test_modern_resource_changes_use_subscription_bus(self) -> None:
        ctx = SimpleNamespace(
            protocol_version=LATEST_MODERN_VERSION,
            notify_resources_changed=mock.AsyncMock(),
        )

        asyncio.run(mcp_server._notify_resource_list_changed(ctx))

        ctx.notify_resources_changed.assert_awaited_once_with()
