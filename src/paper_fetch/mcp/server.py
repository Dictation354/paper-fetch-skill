"""MCP server entrypoint for paper-fetch."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.resources import FileResource, FunctionResource
from mcp.types import CallToolResult, ToolAnnotations

from ..config import build_runtime_env, resolve_mcp_download_dir
from ._instructions import fetch_tool_description, server_instructions
from .cache_index import (
    CACHE_INDEX_RESOURCE_URI,
    CACHED_RESOURCE_TEMPLATE,
    CACHED_RESOURCE_URI_PREFIX,
    cache_scope_id,
    cached_resource_uri,
    is_text_mime_type,
    list_cache_entries,
    scoped_cache_index_resource_uri,
    scoped_cached_resource_uri,
    scoped_cached_resource_uri_prefix,
)
from .output_schemas import (
    BatchCheckOutput,
    BatchResolveOutput,
    FetchPaperOutput,
    GetCachedOutput,
    HasFulltextOutput,
    ListCachedOutput,
    ProviderStatusOutput,
    ResolvePaperOutput,
)
from .prompts import summarize_paper_prompt, verify_citation_list_prompt
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
    provider_status_tool,
    resolve_paper_tool,
)


def _default_download_dir() -> Path:
    return resolve_mcp_download_dir(build_runtime_env())


def _parse_download_dir(download_dir: str | None) -> Path | None:
    text = str(download_dir or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def _cache_index_resource_payload(download_dir: Path | None = None) -> dict[str, object]:
    tool_kwargs: dict[str, object] = {}
    if download_dir is not None:
        tool_kwargs["download_dir"] = download_dir
    return list_cached_payload(**tool_kwargs)


def _read_only_annotations(*, open_world: bool) -> ToolAnnotations:
    return ToolAnnotations(
        readOnlyHint=True,
        openWorldHint=open_world,
    )


def _fetch_annotations() -> ToolAnnotations:
    return ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )


def _sync_cache_resources(
    server: FastMCP,
    *,
    download_dir: Path,
    scope_id: str | None = None,
) -> None:
    entries = list_cache_entries(download_dir)
    resources = server._resource_manager._resources

    def default_entry_uri(entry_id: object) -> str:
        return cached_resource_uri(str(entry_id))

    def scoped_entry_uri(entry_id: object) -> str:
        assert scope_id is not None
        return scoped_cached_resource_uri(scope_id, str(entry_id))

    if scope_id is None:
        index_uri = CACHE_INDEX_RESOURCE_URI
        entry_uri_for = default_entry_uri
        entry_prefix = CACHED_RESOURCE_URI_PREFIX
        name = "cache_index"
        description = "JSON index of cached MCP downloads in the default shared download directory."
    else:
        index_uri = scoped_cache_index_resource_uri(scope_id)
        entry_uri_for = scoped_entry_uri
        entry_prefix = scoped_cached_resource_uri_prefix(scope_id)
        name = f"cache_index_{scope_id}"
        description = (
            "JSON index of cached MCP downloads in an isolated download directory. "
            f"Scope id: {scope_id}."
        )

    def index_payload_for_download_dir() -> dict[str, object]:
        return _cache_index_resource_payload(download_dir)

    resources[index_uri] = FunctionResource.from_function(
        index_payload_for_download_dir,
        uri=index_uri,
        name=name,
        description=description,
        mime_type="application/json",
    )

    active_uris = {entry_uri_for(entry["id"]) for entry in entries}
    stale_uris = [uri for uri in list(resources) if uri.startswith(entry_prefix) and uri not in active_uris]
    for uri in stale_uris:
        del resources[uri]

    for entry in entries:
        uri = entry_uri_for(entry["id"])
        resources[uri] = FileResource(
            uri=uri,
            name=f"cached_{entry['id']}",
            description=f"Cached {entry['kind']} for DOI {entry['doi']}.",
            path=Path(str(entry["path"])),
            mime_type=str(entry["mime"]),
            is_binary=not is_text_mime_type(str(entry["mime"])),
        )


def _sync_resources_for_download_dir(server: FastMCP, download_dir: Path | None) -> None:
    if download_dir is None:
        _sync_cache_resources(server, download_dir=_default_download_dir())
        return
    _sync_cache_resources(server, download_dir=download_dir, scope_id=cache_scope_id(download_dir))


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

    _sync_resources_for_download_dir(server, None)

    @server.prompt(
        name="summarize_paper",
        description="Template for summarizing one known paper with cache-first and provenance-aware fetch discipline.",
    )
    def summarize_paper(query: str, focus: str = "general") -> str:
        return summarize_paper_prompt(query=query, focus=focus)

    @server.prompt(
        name="verify_citation_list",
        description="Template for checking a citation list with batch-first probe discipline.",
    )
    def verify_citation_list(citations: str, mode: str = "metadata") -> str:
        return verify_citation_list_prompt(citations=citations, mode=mode)

    @server.tool(
        name="resolve_paper",
        description="Resolve a DOI, URL, or title query into a normalized paper candidate.",
        annotations=_read_only_annotations(open_world=True),
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
        annotations=_read_only_annotations(open_world=True),
        structured_output=True,
    )
    def has_fulltext(query: str) -> Annotated[CallToolResult, HasFulltextOutput]:
        return has_fulltext_tool(query=query)

    @server.tool(
        name="fetch_paper",
        description=fetch_tool_description(),
        annotations=_fetch_annotations(),
        structured_output=True,
    )
    async def fetch_paper(
        query: str,
        modes: list[str] | None = None,
        strategy: FetchStrategyInput | None = None,
        include_refs: str | None = None,
        max_tokens: int | str = "full_text",
        prefer_cache: bool = False,
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
            prefer_cache=prefer_cache,
            ctx=ctx,
            **tool_kwargs,
        )
        if not result.isError:
            _sync_resources_for_download_dir(server, parsed_download_dir)
        return result

    @server.tool(
        name="list_cached",
        description="List cached downloads known to the MCP cache index without touching the network.",
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    def list_cached(download_dir: str | None = None) -> Annotated[CallToolResult, ListCachedOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, object] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = list_cached_tool(**tool_kwargs)
        if not result.isError:
            _sync_resources_for_download_dir(server, parsed_download_dir)
        return result

    @server.tool(
        name="get_cached",
        description="Look up cached downloads for a DOI in the cache index and return preferred local files.",
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    def get_cached(doi: str, download_dir: str | None = None) -> Annotated[CallToolResult, GetCachedOutput]:
        parsed_download_dir = _parse_download_dir(download_dir)
        tool_kwargs: dict[str, object] = {}
        if parsed_download_dir is not None:
            tool_kwargs["download_dir"] = parsed_download_dir
        result = get_cached_tool(doi=doi, **tool_kwargs)
        if not result.isError:
            _sync_resources_for_download_dir(server, parsed_download_dir)
        return result

    @server.tool(
        name="batch_resolve",
        description="Resolve multiple DOI, URL, or title queries with shared transport reuse and optional cross-host concurrency.",
        annotations=_read_only_annotations(open_world=True),
        structured_output=True,
    )
    async def batch_resolve(
        queries: list[str],
        concurrency: int = 1,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BatchResolveOutput]:
        return await batch_resolve_tool_async(queries=queries, concurrency=concurrency, ctx=ctx)

    @server.tool(
        name="batch_check",
        description=(
            "Check multiple papers without returning full bodies, with optional cross-host concurrency. "
            "Success items keep only lightweight provenance fields."
        ),
        annotations=_read_only_annotations(open_world=True),
        structured_output=True,
    )
    async def batch_check(
        queries: list[str],
        mode: str = "metadata",
        concurrency: int = 1,
        ctx: Context | None = None,
    ) -> Annotated[CallToolResult, BatchCheckOutput]:
        return await batch_check_tool_async(queries=queries, mode=mode, concurrency=concurrency, ctx=ctx)

    @server.tool(
        name="provider_status",
        description="Inspect local provider configuration and runtime readiness without calling remote publisher APIs.",
        annotations=_read_only_annotations(open_world=False),
        structured_output=True,
    )
    def provider_status() -> Annotated[CallToolResult, ProviderStatusOutput]:
        return provider_status_tool()

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
