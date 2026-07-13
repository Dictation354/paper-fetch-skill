"""MCP adapter package for paper-fetch."""

from typing import Any


def __getattr__(name: str) -> Any:
    """Load the server lazily so leaf MCP helpers remain import-cycle safe."""

    if name in {"build_server", "main"}:
        from .server import build_server, main

        return {"build_server": build_server, "main": main}[name]
    raise AttributeError(name)


__all__ = ["build_server", "main"]
