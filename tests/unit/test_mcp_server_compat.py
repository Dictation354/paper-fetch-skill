from __future__ import annotations

import unittest
from types import SimpleNamespace

from mcp.server.fastmcp import FastMCP

from paper_fetch.mcp.server_compat import (
    FastMCPCompatError,
    enable_resource_list_changed_capability,
    resource_registry,
)


class McpServerCompatTests(unittest.TestCase):
    def test_resource_registry_returns_fastmcp_private_registry(self) -> None:
        resources: dict[str, object] = {}
        server = SimpleNamespace(_resource_manager=SimpleNamespace(_resources=resources))

        self.assertIs(resource_registry(server), resources)

    def test_resource_registry_failure_has_readable_error(self) -> None:
        server = SimpleNamespace(_resource_manager=SimpleNamespace())

        with self.assertRaises(FastMCPCompatError) as context:
            resource_registry(server)

        self.assertIn("FastMCP compatibility layer failed", str(context.exception))
        self.assertIn("_resources", str(context.exception))

    def test_enable_resource_list_changed_capability_sets_initialization_options(self) -> None:
        server = FastMCP(name="compat-test", json_response=True)

        enable_resource_list_changed_capability(server)
        options = server._mcp_server.create_initialization_options()

        self.assertIsNotNone(options.capabilities.resources)
        self.assertTrue(options.capabilities.resources.listChanged)


if __name__ == "__main__":
    unittest.main()
