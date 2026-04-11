"""MCP server entrypoint for paper-fetch."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

from .schemas import FetchStrategyInput
from .tools import fetch_paper_tool, resolve_paper_tool


def build_server() -> FastMCP:
    server = FastMCP(
        name="paper-fetch",
        instructions=(
            "Resolve or fetch a specific paper by DOI, landing URL, or title query. "
            "Use resolve_paper when the query may be ambiguous, and fetch_paper when you need "
            "structured article metadata and/or AI-friendly markdown. "
            "By default fetch_paper returns article+markdown, uses asset_profile='none', "
            "and max_tokens='full_text'."
        ),
        json_response=True,
    )

    @server.tool(
        name="resolve_paper",
        description="Resolve a DOI, URL, or title query into a normalized paper candidate.",
        structured_output=False,
    )
    def resolve_paper(query: str) -> CallToolResult:
        return resolve_paper_tool(query=query)

    @server.tool(
        name="fetch_paper",
        description=(
            "Fetch AI-friendly paper content. Returns a fixed FetchEnvelope-style object with "
            "top-level provenance and optional article/markdown/metadata payloads. "
            "Defaults: modes=['article','markdown'], strategy.asset_profile='none', "
            "max_tokens='full_text'. Use strategy.asset_profile='body' or 'all' to include local assets."
        ),
        structured_output=False,
    )
    def fetch_paper(
        query: str,
        modes: list[str] | None = None,
        strategy: FetchStrategyInput | None = None,
        include_refs: str | None = None,
        max_tokens: int | str = "full_text",
    ) -> CallToolResult:
        return fetch_paper_tool(
            query=query,
            modes=modes,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
        )

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
