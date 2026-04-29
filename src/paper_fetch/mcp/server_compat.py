"""Compatibility wrappers for FastMCP SDK internals used by this server."""

from __future__ import annotations

from types import MethodType
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel.server import NotificationOptions


class FastMCPCompatError(RuntimeError):
    """Raised when an expected FastMCP private SDK surface changes."""


def _compat_error(detail: str) -> FastMCPCompatError:
    return FastMCPCompatError(f"FastMCP compatibility layer failed: {detail}")


def resource_registry(server: FastMCP) -> dict[str, object]:
    manager = getattr(server, "_resource_manager", None)
    if manager is None:
        raise _compat_error("server._resource_manager is unavailable; cache resources cannot be synchronized.")
    resources = getattr(manager, "_resources", None)
    if not isinstance(resources, dict):
        raise _compat_error("server._resource_manager._resources is unavailable or is not a dict.")
    return resources


def lowlevel_server(server: FastMCP) -> Any:
    mcp_server = getattr(server, "_mcp_server", None)
    if mcp_server is None:
        raise _compat_error("server._mcp_server is unavailable; stdio transport cannot be started.")
    return mcp_server


def create_initialization_options(server: FastMCP) -> Any:
    mcp_server = lowlevel_server(server)
    create_options = getattr(mcp_server, "create_initialization_options", None)
    if not callable(create_options):
        raise _compat_error("server._mcp_server.create_initialization_options is unavailable.")
    return create_options()


def enable_resource_list_changed_capability(server: FastMCP) -> None:
    mcp_server = lowlevel_server(server)
    original_create_initialization_options = getattr(mcp_server, "create_initialization_options", None)
    if not callable(original_create_initialization_options):
        raise _compat_error("server._mcp_server.create_initialization_options is unavailable.")

    def create_options_with_resource_notifications(
        _mcp_server: object,
        notification_options: NotificationOptions | None = None,
        experimental_capabilities: dict[str, dict[str, object]] | None = None,
    ):
        merged_notification_options = NotificationOptions(
            prompts_changed=notification_options.prompts_changed if notification_options is not None else False,
            resources_changed=True,
            tools_changed=notification_options.tools_changed if notification_options is not None else False,
        )
        return original_create_initialization_options(
            notification_options=merged_notification_options,
            experimental_capabilities=experimental_capabilities,
        )

    mcp_server.create_initialization_options = MethodType(
        create_options_with_resource_notifications,
        mcp_server,
    )


async def run_stdio_server(server: FastMCP, read_stream: Any, write_stream: Any) -> None:
    mcp_server = lowlevel_server(server)
    run = getattr(mcp_server, "run", None)
    if not callable(run):
        raise _compat_error("server._mcp_server.run is unavailable.")
    await run(
        read_stream,
        write_stream,
        create_initialization_options(server),
    )
