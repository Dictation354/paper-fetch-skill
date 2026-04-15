"""MCP server entrypoint for paper-fetch."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.resources import FileResource, FunctionResource
from mcp.types import CallToolResult

from ..config import build_runtime_env, resolve_mcp_download_dir
from ._instructions import fetch_tool_description, server_instructions
from .cache_index import (
    CACHE_INDEX_RESOURCE_URI,
    CACHED_RESOURCE_TEMPLATE,
    CACHED_RESOURCE_URI_PREFIX,
    cached_resource_uri,
    is_text_mime_type,
    list_cache_entries,
)
from .output_schemas import (
    BatchCheckOutput,
    BatchResolveOutput,
    FetchPaperOutput,
    GetCachedOutput,
    HasFulltextOutput,
    ListCachedOutput,
    ResolvePaperOutput,
)
from .schemas import FetchStrategyInput
from .tools import (
    batch_check_tool_async,
    batch_resolve_tool_async,
    cached_entry_payload,
    fetch_paper_tool_async,
    has_fulltext_tool,
    get_cached_tool,
    list_cached_payload,
    list_cached_tool,
    resolve_paper_tool,
)


def _default_download_dir() -> Path:
    return resolve_mcp_download_dir(build_runtime_env())


def _parse_download_dir(download_dir: str | None) -> Path | None:
    text = str(download_dir or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def _cache_index_resource_payload() -> dict[str, object]:
    return list_cached_payload()


def _sync_default_cache_resources(server: FastMCP) -> None:
    download_dir = _default_download_dir()
    entries = list_cache_entries(download_dir)
    active_uris = {cached_resource_uri(str(entry["id"])) for entry in entries}
    resources = server._resource_manager._resources

    stale_uris = [uri for uri in list(resources) if uri.startswith(CACHED_RESOURCE_URI_PREFIX) and uri not in active_uris]
    for uri in stale_uris:
        del resources[uri]

    for entry in entries:
        uri = cached_resource_uri(str(entry["id"]))
        resources[uri] = FileResource(
            uri=uri,
            name=f"cached_{entry['id']}",
            description=f"Cached {entry['kind']} for DOI {entry['doi']}.",
            path=Path(str(entry["path"])),
            mime_type=str(entry["mime"]),
            is_binary=not is_text_mime_type(str(entry["mime"])),
        )


def build_server() -> FastMCP:
    server = FastMCP(
        name="paper-fetch",
        instructions=server_instructions(),
        json_response=True,
    )

    server.add_resource(
        FunctionResource.from_function(
            _cache_index_resource_payload,
            uri=CACHE_INDEX_RESOURCE_URI,
            name="cache_index",
            description="JSON index of cached MCP downloads in the default shared download directory.",
            mime_type="application/json",
        )
    )

    @server.resource(
        CACHED_RESOURCE_TEMPLATE,
        name="cached_entry_template",
        description="Read a cached file from the default shared MCP download directory by entry id.",
        mime_type="application/octet-stream",
    )
    def cached_entry_resource(entry_id: str) -> str | bytes:
        entry = cached_entry_payload(entry_id=entry_id)
        if entry is None:
            raise FileNotFoundError(f"Unknown cached entry: {entry_id}")
        path = Path(str(entry["path"]))
        if is_text_mime_type(str(entry["mime"])):
            return path.read_text(encoding="utf-8")
        return path.read_bytes()

    _sync_default_cache_resources(server)

    @server.tool(
        name="resolve_paper",
        description="Resolve a DOI, URL, or title query into a normalized paper candidate.",
        structured_output=True,
    )
    def resolve_paper(
        query: str | None = None,
        title: str | None = None,
        authors: list[str] | str | None = None,
        year: int | None = None,
    ) -> Annotated[CallToolResult, ResolvePaperOutput]:
        return resolve_paper_tool(
            query=query,
            title=title,
            authors=authors,
            year=year,
        )

    @server.tool(
        name="has_fulltext",
        description="Probe whether a paper likely has accessible full text using cheap metadata and landing-page signals.",
        structured_output=True,
    )
    def has_fulltext(query: str) -> Annotated[CallToolResult, HasFulltextOutput]:
        return has_fulltext_tool(query=query)

    @server.tool(
        name="fetch_paper",
        description=fetch_tool_description(),
        structured_output=True,
    )
    async def fetch_paper(
        query: str,
        modes: list[str] | None = None,
        strategy: FetchStrategyInput | None = None,
        include_refs: str | None = None,
        max_tokens: int | str = "full_text",
        download_dir: str | None = None,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, FetchPaperOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, object] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = await fetch_paper_tool_async(
            query=query,
            modes=modes,
            strategy=strategy,
            include_refs=include_refs,
            max_tokens=max_tokens,
            ctx=ctx,
            **tool_kwargs,
        )
        if parsed_download_dir is None and not result.isError:
            _sync_default_cache_resources(server)
        return result

    @server.tool(
        name="list_cached",
        description="List cached downloads known to the MCP cache index without touching the network.",
        structured_output=True,
    )
    def list_cached(download_dir: str | None = None) -> Annotated[CallToolResult, ListCachedOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, object] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = list_cached_tool(**tool_kwargs)
        if parsed_download_dir is None and not result.isError:
            _sync_default_cache_resources(server)
        return result

    @server.tool(
        name="get_cached",
        description="Look up cached downloads for a DOI in the cache index and return preferred local files.",
        structured_output=True,
    )
    def get_cached(doi: str, download_dir: str | None = None) -> Annotated[CallToolResult, GetCachedOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, object] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = get_cached_tool(doi=doi, **tool_kwargs)
        if parsed_download_dir is None and not result.isError:
            _sync_default_cache_resources(server)
        return result

    @server.tool(
        name="batch_resolve",
        description="Resolve multiple DOI, URL, or title queries serially with shared transport reuse.",
        structured_output=True,
    )
    async def batch_resolve(queries: list[str], ctx: Context | None = None) -> Annotated[CallToolResult, BatchResolveOutput]:
        return await batch_resolve_tool_async(queries=queries, ctx=ctx)

    @server.tool(
        name="batch_check",
        description=(
            "Check multiple papers serially without returning full bodies. "
            "Success items keep only lightweight provenance fields."
        ),
        structured_output=True,
    )
    async def batch_check(
        queries: list[str],
        mode: str = "metadata",
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BatchCheckOutput]:
        return await batch_check_tool_async(queries=queries, mode=mode, ctx=ctx)

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
